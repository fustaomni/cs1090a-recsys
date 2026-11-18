"""A result reaches the site only through site:record, validated and tied to its run (A.95)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import site_record
from nonvacuous import nonempty
from site_record import ROOT, Estimate, Metrics, load, recorded

TODAY = dt.date(2026, 11, 30)
BASELINES = ["global-mean", "user-mean", "movie-mean", "bias"]
EXPECTED = [
    *(f"baseline:{name}" for name in BASELINES),
    *(f"model:{n}" for n in range(1, 13)),
    "model:15",
]


def _metrics() -> Metrics:
    estimate = Estimate(value=0.9, low=0.88, high=0.92)
    return Metrics(rmse=estimate, mae=estimate, rmsem=estimate, maem=estimate)


def test_the_site_results_validate_and_cover_every_row() -> None:
    results = load(ROOT)
    assert [row.key for row in results.rows] == EXPECTED
    assert results.primary.status == "pending"


def test_the_board_holds_a_pending_mixture_row() -> None:
    """A.346: the results board holds the mixture of experts, pending, for Milestone 4."""
    rows = load(ROOT).rows
    row = next((row for row in rows if row.key == "model:15"), None)
    assert row is not None, [row.key for row in rows]
    assert (row.kind, row.milestone, row.status) == ("model", "M4", "pending"), row


def test_a_measured_row_is_recorded_with_its_run() -> None:
    updated = recorded(load(ROOT), "baseline:bias", "run-123", _metrics(), TODAY)
    row = next(row for row in updated.rows if row.key == "baseline:bias")
    assert (row.status, row.run_id, row.metrics) == ("measured", "run-123", _metrics())
    assert updated.updated == "2026-11-30"
    assert all(other.status == "pending" for other in nonempty(updated.rows) if other is not row)


def test_an_unknown_row_is_refused() -> None:
    with pytest.raises(SystemExit, match="no results row"):
        recorded(load(ROOT), "model:13", "run-123", _metrics(), TODAY)


def test_an_interval_that_excludes_its_value_is_refused() -> None:
    with pytest.raises(ValidationError, match="excludes"):
        Estimate(value=0.95, low=0.88, high=0.92)


def test_every_m2_finding_names_its_pointer_and_digest(tmp_path: Path) -> None:
    """A.349: each recorded M2 entry names the pointer it was read by and the file's digest."""
    source = tmp_path / "results.json"
    source.write_text(json.dumps({"quality": [{"status": "pass", "count": 0}]}), encoding="utf-8")
    pointers = {
        "Ratings outside 1 to 5": "/quality/0/count",
        "Ratings outside 1 to 5: verdict": "/quality/0/status",
    }
    updated = site_record.sectioned(load(ROOT), "M2", source, "ms2-results/v1", pointers, TODAY)
    section = next(s for s in updated.milestones if s.milestone == "M2")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    named = [
        (entry.label, getattr(entry, "pointer", None), entry.evidence.sha256)
        for entry in nonempty(section.entries)
    ]
    assert named == [(label, pointer, digest) for label, pointer in pointers.items()], named


def test_a_milestone_section_is_recorded_from_its_results_file(tmp_path: Path) -> None:
    """A.342: each entry is read by its JSON pointer and names its file's digest."""
    found = tmp_path / "results.json"
    found.write_text(json.dumps({"split": {"train": 8, "test": 2}}), encoding="utf-8")
    pointers = {"training ratings": "/split/train", "test ratings": "/split/test"}
    updated = site_record.sectioned(load(ROOT), "M2", found, "ms2-results/v1", pointers, TODAY)
    section = next(entry for entry in updated.milestones if entry.milestone == "M2")
    shown = [(entry.label, entry.value) for entry in section.entries]
    assert shown == [("training ratings", 8), ("test ratings", 2)], shown
    digest = hashlib.sha256(found.read_bytes()).hexdigest()
    named = {(e.evidence.contract, e.evidence.sha256) for e in nonempty(section.entries)}
    assert named == {("ms2-results/v1", digest)}, named


def test_a_pointer_the_results_file_lacks_is_refused(tmp_path: Path) -> None:
    """A.342: a pointer the file lacks is refused, by name, before anything is written."""
    found = tmp_path / "results.json"
    found.write_text(json.dumps({"split": {"train": 8}}), encoding="utf-8")
    pointers = {"missing": "/split/missing"}
    with pytest.raises(SystemExit, match="/split/missing"):
        site_record.sectioned(load(ROOT), "M2", found, "ms2-results/v1", pointers, TODAY)
