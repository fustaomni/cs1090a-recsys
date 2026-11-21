# tests/test_reproduce.py
"""Reproducibility is tested automatically (A.287).

A recorded offline run is re-run from its evidence record alone, its data snapshot, seeds,
protocol and commit, and its metrics must match the recorded ones within a declared tolerance;
a data snapshot that differs from the recorded one is refused before anything re-runs.
"""

from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType

import pytest

from evaluation_evidence import DataSnapshot, EvaluationEvidence, Metric

TEST = "c" * 64


def _subject() -> ModuleType:
    found = importlib.util.find_spec("reproduce")
    assert found is not None, "scripts/reproduce.py does not exist"
    return importlib.import_module("reproduce")


def _recorded() -> EvaluationEvidence:
    snapshot = DataSnapshot(archive_sha256="a" * 64, train_sha256="b" * 64, test_sha256=TEST)
    rmse = Metric(name="rmse", value=0.9, low=0.88, high=0.92, model_id="bias", dataset_digest=TEST)
    return EvaluationEvidence(
        run_id="run-1",
        data_snapshot=snapshot,
        protocol_digest="d" * 64,
        seeds=(7,),
        code_commit="e" * 40,
        environment_lock="f" * 64,
        tuning_budget=20,
        metrics=(rmse,),
    )


def test_a_rerun_from_its_evidence_reproduces_its_metrics() -> None:
    subject = _subject()
    recorded = _recorded()
    seen: list[EvaluationEvidence] = []

    def rerun(evidence: EvaluationEvidence) -> dict[str, float]:
        seen.append(evidence)
        return {"rmse": 0.9 + 1e-9}

    result = subject.reproduce(recorded, recorded.data_snapshot, rerun, tolerance=1e-6)
    assert seen == [recorded], seen
    assert result.reproduced, result
    drifted = subject.reproduce(
        recorded, recorded.data_snapshot, lambda _: {"rmse": 0.95}, tolerance=1e-6
    )
    assert not drifted.reproduced, drifted
    assert set(drifted.differences) == {"rmse"}, drifted


def test_a_changed_data_snapshot_is_refused_before_rerunning() -> None:
    subject = _subject()
    recorded = _recorded()
    changed = recorded.data_snapshot.model_copy(update={"test_sha256": "0" * 64})
    calls: list[EvaluationEvidence] = []

    def rerun(evidence: EvaluationEvidence) -> dict[str, float]:
        calls.append(evidence)
        return {"rmse": 0.9}

    with pytest.raises(subject.SnapshotChangedError, match="test_sha256"):
        subject.reproduce(recorded, changed, rerun, tolerance=1e-6)
    assert calls == [], calls
