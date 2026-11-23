# tests/test_prediction_evidence.py
"""Every offline prediction is recorded as typed, append-only evidence (A.296).

A record names its model and version, its evaluator and MLflow runs, the dataset digest, the
explanation method and version, and each feature's cutoffs by event and observation time, both
strictly before the prediction; the outcome is never part of it. The log chains each record to
the one before, so a record appended again with other content, or edited in place, is refused.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pydantic import ValidationError

DIGEST = "a" * 64


def _subject() -> ModuleType:
    found = importlib.util.find_spec("prediction_evidence")
    assert found is not None, "scripts/prediction_evidence.py does not exist"
    return importlib.import_module("prediction_evidence")


def _record(subject: ModuleType, **changes: object) -> Any:
    fields: dict[str, object] = {
        "prediction_id": "p-1",
        "predicted_at": 1000,
        "predicted_rating": 3.7,
        "model_id": "moe",
        "model_version": "1",
        "evaluator_run": "run-1",
        "mlflow_run": "mlflow-1",
        "dataset_digest": DIGEST,
        "explanation_method": "additive-terms",
        "explanation_version": "1",
        "features": (
            subject.FeatureProvenance(name="user_mean", event_cutoff=990, observation_cutoff=995),
        ),
    }
    return subject.PredictionRecord.model_validate({**fields, **changes})


def test_every_prediction_names_its_model_and_feature_cutoffs() -> None:
    subject = _subject()
    record = _record(subject)
    assert (record.model_id, record.model_version) == ("moe", "1")
    assert record.features[0].observation_cutoff == 995
    with pytest.raises(ValidationError):
        _record(subject, features=())
    with pytest.raises(ValidationError):
        _record(subject, outcome=4)
    late = subject.FeatureProvenance(name="user_mean", event_cutoff=990, observation_cutoff=1000)
    with pytest.raises(ValidationError):
        _record(subject, features=(late,))


def test_a_rewritten_prediction_record_is_refused(tmp_path: Path) -> None:
    subject = _subject()
    log = subject.PredictionLog(tmp_path / "predictions.jsonl")
    log.append(_record(subject))
    log.append(_record(subject, prediction_id="p-2"))
    with pytest.raises(subject.RewrittenRecordError):
        log.append(_record(subject, predicted_rating=4.9))
    assert [each.prediction_id for each in log.read()] == ["p-1", "p-2"]
    path = tmp_path / "predictions.jsonl"
    path.write_text(path.read_text(encoding="utf-8").replace("3.7", "4.9", 1), encoding="utf-8")
    with pytest.raises(subject.RewrittenRecordError):
        log.read()
