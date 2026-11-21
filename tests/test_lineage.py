# tests/test_lineage.py
"""Every offline pipeline stage records its lineage as OpenLineage run events (A.293).

Each stage writes one START event and exactly one COMPLETE or FAIL event as JSON files, sharing
one run id and naming its input and output datasets with their digests, so every evidence run
traces back through the stages to the three MovieLens files.
"""

from __future__ import annotations

import importlib
import importlib.util
import uuid
from pathlib import Path
from types import ModuleType

import pytest

REQUIRED = {"eventType", "eventTime", "producer", "schemaURL", "run", "job"}


def _subject() -> ModuleType:
    found = importlib.util.find_spec("lineage")
    assert found is not None, "scripts/lineage.py does not exist"
    return importlib.import_module("lineage")


def test_every_stage_emits_openlineage_start_and_complete_events(tmp_path: Path) -> None:
    subject = _subject()
    with subject.stage(tmp_path, "load", {"ratings.dat": "a" * 64}, {"ratings": "b" * 64}):
        pass
    start, complete = subject.events(tmp_path)
    assert (start["eventType"], complete["eventType"]) == ("START", "COMPLETE"), start
    assert start["run"]["runId"] == complete["run"]["runId"], complete
    uuid.UUID(start["run"]["runId"])
    for event in (start, complete):
        assert set(event) >= REQUIRED, event
        assert event["job"]["name"] == "load", event
    assert [each["name"] for each in complete["inputs"]] == ["ratings.dat"], complete
    assert [each["name"] for each in complete["outputs"]] == ["ratings"], complete
    with pytest.raises(RuntimeError), subject.stage(tmp_path, "split", {"ratings": "b" * 64}, {}):
        raise RuntimeError("the stage failed")
    assert subject.events(tmp_path)[-1]["eventType"] == "FAIL"


def test_every_evidence_run_traces_back_to_the_movielens_files(tmp_path: Path) -> None:
    subject = _subject()
    files = {"ratings.dat": "1" * 64, "users.dat": "2" * 64, "movies.dat": "3" * 64}
    with subject.stage(tmp_path, "load", files, {"table": "4" * 64}):
        pass
    halves = {"train": "5" * 64, "test": "6" * 64}
    with subject.stage(tmp_path, "split", {"table": "4" * 64}, halves):
        pass
    with subject.stage(tmp_path, "evaluate", {"train": "5" * 64}, {"evidence": "7" * 64}):
        pass
    assert subject.trace(tmp_path, "evidence") == set(files), subject.events(tmp_path)
