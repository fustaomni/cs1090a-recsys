# tests/test_evaluation_contracts.py
"""The evidence, verdict and decision boundary is typed in Pydantic v2 (A.302).

An EvaluationPolicy declares how a comparison is judged; a ComparisonEvidence refuses an
interval out of order or one that excludes its own estimate, and is admitted only under the
interval method its policy declares; an EvaluationResult names the digests it was reached from.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
from types import ModuleType

import pytest
from pydantic import ValidationError

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _subject() -> ModuleType:
    found = importlib.util.find_spec("evaluation_contracts")
    assert found is not None, "scripts/evaluation_contracts.py does not exist"
    return importlib.import_module("evaluation_contracts")


def _policy(subject: ModuleType) -> object:
    return subject.EvaluationPolicy(
        test_statistic="user-level sign-flip permutation test of paired per-user differences",
        interval_method=subject.IntervalMethod.USER_BOOTSTRAP,
        significance_level=0.05,
        practical_threshold=0.009,
        disagreement=subject.Verdict.INCONCLUSIVE,
    )


def _evidence(subject: ModuleType, **changes: object) -> object:
    fields: dict[str, object] = {
        "model_id": "moe",
        "baseline_id": "bias",
        "estimate": 0.02,
        "low": -0.005,
        "high": 0.045,
        "p_value": 0.2,
        "interval_method": subject.IntervalMethod.USER_BOOTSTRAP,
    }
    fields.update(changes)
    return subject.ComparisonEvidence(**fields)


def test_an_interval_that_excludes_its_estimate_is_refused() -> None:
    subject = _subject()
    _evidence(subject)
    with pytest.raises(ValidationError, match="excludes"):
        _evidence(subject, estimate=0.05)
    with pytest.raises(ValidationError, match="order"):
        _evidence(subject, low=0.045, high=-0.005)


def test_evidence_built_by_an_undeclared_interval_method_is_refused() -> None:
    subject = _subject()
    policy = _policy(subject)
    declared = _evidence(subject)
    assert subject.admit(policy, declared) == declared
    undeclared = _evidence(subject, interval_method=subject.IntervalMethod.SPLIT_CONFORMAL)
    with pytest.raises(subject.UndeclaredMethodError, match="split-conformal"):
        subject.admit(policy, undeclared)


def test_a_result_names_its_policy_and_evidence_digests() -> None:
    subject = _subject()
    policy = _policy(subject)
    evidence = _evidence(subject)
    result = subject.EvaluationResult(
        verdict=subject.Verdict.INCONCLUSIVE,
        action=subject.Action.RECORD_INSUFFICIENT_EVIDENCE,
        policy_digest=subject.digest(policy),
        evidence_digest=subject.digest(evidence),
    )
    assert SHA256.match(result.policy_digest), result
    assert SHA256.match(result.evidence_digest), result
    assert result.policy_digest != result.evidence_digest, result
    with pytest.raises(ValidationError):
        subject.EvaluationResult(
            verdict=subject.Verdict.INCONCLUSIVE,
            action=subject.Action.RECORD_INSUFFICIENT_EVIDENCE,
            policy_digest=subject.digest(policy),
        )
    with pytest.raises(ValidationError):
        result.verdict = subject.Verdict.SUPPORTED
