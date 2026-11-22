# scripts/lineage.py
"""Every offline pipeline stage records its lineage as OpenLineage run events (A.293).

A stage writes one START event when it begins and exactly one COMPLETE or FAIL event when it
ends, as JSON files sharing one run id, in the OpenLineage 2-0-2 RunEvent shape: eventTime,
producer, schemaURL, run, job, and the input and output datasets, each with its SHA-256. The
COMPLETE events then form a graph, so any evidence dataset traces back to the source files.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from project_identity import load

# The job namespace and producer are this project's declared identity, never a copy (D.52).
IDENTITY = load()
NAMESPACE = IDENTITY.name
PRODUCER = IDENTITY.repository
SCHEMA = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"
DIGEST_FACET = f"{PRODUCER}/blob/develop/scripts/lineage.py#sha256"


def _datasets(named: Mapping[str, str]) -> list[dict[str, Any]]:
    facet = {"_producer": PRODUCER, "_schemaURL": DIGEST_FACET}
    return [
        {"namespace": NAMESPACE, "name": name, "facets": {"sha256": {**facet, "value": digest}}}
        for name, digest in named.items()
    ]


def _event(
    kind: str, run_id: str, job: str, inputs: Mapping[str, str], outputs: Mapping[str, str]
) -> dict[str, Any]:
    return {
        "eventType": kind,
        "eventTime": datetime.now(UTC).isoformat(),
        "producer": PRODUCER,
        "schemaURL": SCHEMA,
        "run": {"runId": run_id},
        "job": {"namespace": NAMESPACE, "name": job},
        "inputs": _datasets(inputs),
        "outputs": _datasets(outputs),
    }


def _write(root: Path, event: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    sequence = len(list(root.glob("*.json")))
    path = root / f"{sequence:06d}-{event['eventType']}.json"
    path.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")


@contextmanager
def stage(
    root: Path, job: str, inputs: Mapping[str, str], outputs: Mapping[str, str]
) -> Iterator[str]:
    """Run one stage between its START event and its COMPLETE, or FAIL, event."""
    run_id = str(uuid.uuid4())
    _write(root, _event("START", run_id, job, inputs, {}))
    try:
        yield run_id
    except BaseException:
        _write(root, _event("FAIL", run_id, job, inputs, {}))
        raise
    _write(root, _event("COMPLETE", run_id, job, inputs, outputs))


def events(root: Path) -> list[dict[str, Any]]:
    """Every event under root, in the order the stages wrote them."""
    paths = sorted(root.glob("*.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def trace(root: Path, dataset: str) -> set[str]:
    """The source datasets a dataset was built from, through every completed stage."""
    produced: dict[str, list[str]] = {}
    for event in events(root):
        if event["eventType"] != "COMPLETE":
            continue
        sources = [each["name"] for each in event["inputs"]]
        for output in event["outputs"]:
            produced.setdefault(output["name"], []).extend(sources)
    found: set[str] = set()
    seen: set[str] = set()
    pending = [dataset]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        parents = produced.get(name)
        if parents is None:
            found.add(name)
        else:
            pending.extend(parents)
    return found
