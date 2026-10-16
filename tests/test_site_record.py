"""A result reaches the site only through site:record, validated and tied to its run (A.95)."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from site_record import ROOT, Estimate, Metrics, load, recorded

TODAY = dt.date(2026, 11, 30)
BASELINES = ["global-mean", "user-mean", "film-mean", "bias"]
EXPECTED = [f"baseline:{name}" for name in BASELINES] + [f"model:{n}" for n in range(1, 13)]


def _metrics() -> Metrics:
    estimate = Estimate(value=0.9, low=0.88, high=0.92)
    return Metrics(rmse=estimate, mae=estimate, rmsem=estimate, maem=estimate)


def test_the_site_results_validate_and_cover_every_row() -> None:
    results = load(ROOT)
    assert [row.key for row in results.rows] == EXPECTED
    assert results.primary.status == "pending"


def test_a_measured_row_is_recorded_with_its_run() -> None:
    updated = recorded(load(ROOT), "baseline:bias", "run-123", _metrics(), TODAY)
    row = next(row for row in updated.rows if row.key == "baseline:bias")
    assert (row.status, row.run_id, row.metrics) == ("measured", "run-123", _metrics())
    assert updated.updated == "2026-11-30"
    assert all(other.status == "pending" for other in updated.rows if other is not row)


def test_an_unknown_row_is_refused() -> None:
    with pytest.raises(SystemExit, match="no results row"):
        recorded(load(ROOT), "model:13", "run-123", _metrics(), TODAY)


def test_an_interval_that_excludes_its_value_is_refused() -> None:
    with pytest.raises(ValidationError, match="excludes"):
        Estimate(value=0.95, low=0.88, high=0.92)
