# scripts/evaluation_contracts.py
"""The evidence, verdict and decision boundary, typed in Pydantic v2 (A.302).

An EvaluationPolicy declares how a comparison is judged before any result: its test statistic,
its interval method, its significance level, its practical threshold and the verdict reached
when the interval and the test disagree. ComparisonEvidence is what the statistics produce and
holds no decision; it refuses an interval out of order or one that excludes its own estimate,
and is admitted only under the method its policy declares. An EvaluationResult names the
digests of the policy and the evidence it was reached from, so it can be recomputed.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contract_base import Contract

SHA256 = r"^[0-9a-f]{64}$"


class IntervalMethod(StrEnum):
    """How a paired improvement's interval is built."""

    USER_BOOTSTRAP = "user-bootstrap"
    BAYESIAN_POSTERIOR = "bayesian-posterior"
    SPLIT_CONFORMAL = "split-conformal"


class Verdict(StrEnum):
    """The three verdicts three-sided testing can reach."""

    SUPPORTED = "supported"
    NOT_SUPPORTED = "not-supported"
    INCONCLUSIVE = "inconclusive"


class Action(StrEnum):
    """The one decision each verdict leads to."""

    ACCEPT_RESEARCH_FINDING = "accept-research-finding"
    REJECT_IMPROVEMENT_CLAIM = "reject-improvement-claim"
    RECORD_INSUFFICIENT_EVIDENCE = "record-insufficient-evidence"


class _Frozen(Contract):
    model_config = ConfigDict(frozen=True)


class EvaluationPolicy(_Frozen):
    """How a comparison is judged, declared before any result."""

    test_statistic: str = Field(min_length=1)
    interval_method: IntervalMethod
    significance_level: float = Field(gt=0, lt=1)
    practical_threshold: float = Field(gt=0)
    disagreement: Verdict


class ComparisonEvidence(_Frozen):
    """A paired comparison's estimate, interval and test, and never a decision."""

    model_id: str = Field(min_length=1)
    baseline_id: str = Field(min_length=1)
    estimate: float
    low: float
    high: float
    p_value: float = Field(ge=0, le=1)
    interval_method: IntervalMethod

    @model_validator(mode="after")
    def _interval_holds_its_estimate(self) -> Self:
        if self.low > self.high:
            raise ValueError(f"interval [{self.low}, {self.high}] is out of order")
        if not self.low <= self.estimate <= self.high:
            raise ValueError(f"interval [{self.low}, {self.high}] excludes {self.estimate}")
        return self


class EvaluationResult(_Frozen):
    """A verdict and its decision, naming the policy and evidence they were reached from."""

    verdict: Verdict
    action: Action
    policy_digest: str = Field(pattern=SHA256)
    evidence_digest: str = Field(pattern=SHA256)


class UndeclaredMethodError(ValueError):
    """Evidence built by an interval method its policy does not declare."""


def digest(model: BaseModel) -> str:
    """The SHA-256 of a model's canonical JSON, the same bytes for the same values."""
    canonical = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def admit(policy: EvaluationPolicy, evidence: ComparisonEvidence) -> ComparisonEvidence:
    """The evidence, if it was built by the interval method the policy declares."""
    if evidence.interval_method != policy.interval_method:
        declared = policy.interval_method.value
        raise UndeclaredMethodError(
            f"evidence built by {evidence.interval_method.value}; the policy declares {declared}"
        )
    return evidence
