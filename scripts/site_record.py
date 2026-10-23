"""site:record -- one measured result into the site's results, as a source-apply spec (A.95).

The site's results live in one document, site/src/data/results.json, and nothing types into it
by hand: a result arrives as metrics with intervals and the run that produced them, is validated,
and becomes a spec that rewrites the document exactly as it stands. An unknown row, or an
interval that does not contain its own value, is refused before anything is written.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from contract_base import Contract, from_document

ROOT = Path(__file__).resolve().parent.parent
RESULTS = Path("site") / "src" / "data" / "results.json"
QUOTE = "'" * 3
USAGE = "usage: site:record --out <spec.toml> <row-key> <run-id> <metrics.json>"


class Estimate(Contract):
    """A metric's point estimate and its interval, which must contain it."""

    value: float
    low: float
    high: float

    @model_validator(mode="after")
    def _contains_its_value(self) -> Self:
        if not self.low <= self.value <= self.high:
            raise ValueError(f"interval [{self.low}, {self.high}] excludes {self.value}")
        return self


class Metrics(Contract):
    """The four metrics the design fixed in Phase 0, each with its interval."""

    rmse: Estimate
    mae: Estimate
    rmsem: Estimate
    maem: Estimate


class Row(Contract):
    """One baseline or model on the board, pending until a run measures it."""

    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: Literal["baseline", "model"]
    milestone: str = Field(min_length=1)
    status: Literal["pending", "measured"]
    metrics: Metrics | None = None
    run_id: str | None = None


class Primary(Contract):
    """The pre-registered primary comparison and its possible verdicts, fixed before results."""

    question: str = Field(min_length=1)
    verdicts: tuple[str, ...]
    status: Literal["pending", "decided"]
    verdict: str | None = None


class Results(Contract):
    """site-results/v1: everything the results board shows."""

    contract: Literal["site-results/v1"] = "site-results/v1"
    updated: str
    protocol: str
    primary: Primary
    rows: tuple[Row, ...]


def load(root: Path = ROOT) -> Results:
    """The site's results, validated."""
    return from_document(Results, json.loads((root / RESULTS).read_text(encoding="utf-8")))


def recorded(results: Results, key: str, run_id: str, metrics: Metrics, today: dt.date) -> Results:
    """The results with one row measured by one run; an unknown row is refused."""
    keys = [row.key for row in results.rows]
    if key not in keys:
        raise SystemExit(f"no results row {key!r}; rows are {', '.join(keys)}")
    measured = {"status": "measured", "metrics": metrics, "run_id": run_id}
    rows = tuple(row.model_copy(update=measured) if row.key == key else row for row in results.rows)
    return results.model_copy(update={"rows": rows, "updated": today.isoformat()})


def render(results: Results) -> str:
    """The document as the site reads it: indented JSON, one trailing newline."""
    return json.dumps(results.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"


def _spec(current: str, text: str) -> str:
    head = 'contract = "source-apply/v1"\n\n[[operations]]\nop = "replace"\n'
    target = f'path = "{RESULTS.as_posix()}"\n'
    body = f"anchor = {QUOTE}{current}{QUOTE}\nreplacement = {QUOTE}{text}{QUOTE}\n"
    return head + target + body


def main(argv: Sequence[str] | None = None) -> int:
    """site:record --out <spec> <row-key> <run-id> <metrics.json>."""
    args = list(sys.argv[1:] if argv is None else argv)
    match args:
        case ["--out", out, key, run_id, metrics_path]:
            current = (ROOT / RESULTS).read_text(encoding="utf-8")
            document = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
            metrics = from_document(Metrics, document)
            today = dt.datetime.now(dt.UTC).date()
            updated = recorded(load(ROOT), key, run_id, metrics, today)
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(_spec(current, render(updated)), encoding="utf-8")
            print(f"recorded {key} from {run_id}; apply it with source:apply {out}")
            return 0
        case _:
            raise SystemExit(USAGE)


if __name__ == "__main__":
    sys.exit(main())
