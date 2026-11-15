# tests/test_evaluation_evidence.py
"""Every offline evaluation run's evidence is a validated data structure (A.283).

The record names the data snapshot, the protocol, every seed, the commit, the lock and the
tuning budget; each metric names the model and the dataset it was measured on; and the schema
is committed, so a reader can validate a record without this code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation_evidence import EvaluationEvidence

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "contracts" / "schemas" / "evaluation-evidence-v1.json"
TEST_DIGEST = "c" * 64


def _record(drop: str = "", metric_drop: str = "") -> str:
    """A complete record as JSON, less one top-level field or one metric field."""
    metric: dict[str, object] = {
        "name": "rmse",
        "value": 0.9,
        "low": 0.88,
        "high": 0.92,
        "model_id": "bias-baseline",
        "dataset_digest": TEST_DIGEST,
    }
    record: dict[str, object] = {
        "contract": "evaluation-evidence/v1",
        "run_id": "run-1",
        "data_snapshot": {
            "archive_sha256": "a" * 64,
            "train_sha256": "b" * 64,
            "test_sha256": TEST_DIGEST,
        },
        "protocol_digest": "d" * 64,
        "seeds": [7],
        "code_commit": "e" * 40,
        "environment_lock": "f" * 64,
        "tuning_budget": 20,
        "metrics": [{key: value for key, value in metric.items() if key != metric_drop}],
    }
    return json.dumps({key: value for key, value in record.items() if key != drop})


def test_an_evidence_record_missing_its_data_snapshot_is_refused() -> None:
    EvaluationEvidence.model_validate_json(_record())
    with pytest.raises(ValidationError, match="data_snapshot"):
        EvaluationEvidence.model_validate_json(_record(drop="data_snapshot"))


def test_an_evidence_record_round_trips_the_committed_schema() -> None:
    assert SCHEMA.exists(), f"{SCHEMA.relative_to(ROOT)} is not committed"
    committed: object = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert committed == EvaluationEvidence.model_json_schema()
    evidence = EvaluationEvidence.model_validate_json(_record())
    assert EvaluationEvidence.model_validate_json(evidence.model_dump_json()) == evidence


def test_a_metric_names_the_model_and_dataset_it_was_measured_on() -> None:
    metric = EvaluationEvidence.model_validate_json(_record()).metrics[0]
    assert (metric.model_id, metric.dataset_digest) == ("bias-baseline", TEST_DIGEST)
    with pytest.raises(ValidationError, match="model_id"):
        EvaluationEvidence.model_validate_json(_record(metric_drop="model_id"))
    with pytest.raises(ValidationError, match="dataset_digest"):
        EvaluationEvidence.model_validate_json(_record(metric_drop="dataset_digest"))
