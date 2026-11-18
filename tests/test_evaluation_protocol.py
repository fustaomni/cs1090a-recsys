# tests/test_evaluation_protocol.py
"""Every offline evaluation follows one research policy fixed before any result (A.284).

The policy is a committed file, and every evidence record must name its SHA-256: a record
under any other digest is refused before it is used. The split audit refuses a training
rating dated at or after the test boundary, and reports the users and movies the split
leaves cold.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from evaluation_evidence import EvaluationEvidence
from wrangling import Rating

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = ROOT / "contracts" / "evaluation-protocol.toml"
BOUNDARY = 1_000


def _subject() -> ModuleType:
    found = importlib.util.find_spec("evaluation_protocol")
    assert found is not None, "scripts/evaluation_protocol.py does not exist"
    return importlib.import_module("evaluation_protocol")


def _evidence(protocol_digest: str) -> EvaluationEvidence:
    """A complete evaluation-evidence/v1 record naming the given protocol digest."""
    measured = "c" * 64
    record = {
        "contract": "evaluation-evidence/v1",
        "run_id": "run-1",
        "data_snapshot": {
            "archive_sha256": "a" * 64,
            "train_sha256": "b" * 64,
            "test_sha256": measured,
        },
        "protocol_digest": protocol_digest,
        "seeds": [7],
        "code_commit": "e" * 40,
        "environment_lock": "d" * 64,
        "tuning_budget": 20,
        "metrics": [
            {
                "name": "rmse",
                "value": 0.9,
                "low": 0.88,
                "high": 0.92,
                "model_id": "bias-baseline",
                "dataset_digest": measured,
            }
        ],
    }
    return EvaluationEvidence.model_validate_json(json.dumps(record))


def test_a_record_under_an_undeclared_protocol_is_refused() -> None:
    subject = _subject()
    subject.load(PROTOCOL)
    digest = subject.digest(PROTOCOL)
    assert subject.admit(_evidence(digest), PROTOCOL) == _evidence(digest)
    with pytest.raises(subject.UndeclaredProtocolError, match="f" * 64):
        subject.admit(_evidence("f" * 64), PROTOCOL)


def test_the_split_audit_refuses_a_training_rating_after_the_test_boundary() -> None:
    subject = _subject()
    train = (Rating(1, 10, 4, 998), Rating(2, 11, 3, BOUNDARY))
    test = (Rating(3, 12, 5, BOUNDARY), Rating(1, 10, 2, BOUNDARY + 1))
    with pytest.raises(subject.LeakingSplitError, match=str(BOUNDARY)):
        subject.audit_split(train, test, BOUNDARY)
    report = subject.audit_split(train[:1], test, BOUNDARY)
    assert (report.cold_users, report.cold_movies) == (1, 1), report
