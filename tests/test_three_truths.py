"""Requirement, observation and verdict are kept apart by audit (A.241)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from contract_base import Contract
from spine import Verdict, digest, policy_revision
from truths import audit_observations, completed, recompute, refuse_write, register


class _Observed(Contract):
    rows: int


class _SelfJudged(Contract):
    rows: int
    verified: bool


def _name(model: type[Contract]) -> str:
    return f"{model.__module__}.{model.__qualname__}"


def _verdict(**changes: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "subject": "run",
        "entrypoint": "data.runs.deny",
        "policy_revision": "a" * 64,
        "evidence_digest": "b" * 64,
        "judged_at": datetime(2026, 11, 5, tzinfo=UTC),
        "outcome": "pass",
        "rules": (),
    }
    fields.update(changes)
    return fields


def test_a_task_that_writes_a_requirement_contract_is_refused() -> None:
    truths = register()
    assert refuse_write("data:fetch", "context/plan.toml", truths) == "TRUTH_REQUIREMENT_WRITE"
    assert refuse_write("plan:add", "context/plan.toml", truths) is None
    assert refuse_write("data:fetch", "data/ml-1m/ratings.dat", truths) is None


def test_an_observation_contract_with_a_verdict_field_is_refused() -> None:
    declared = (_name(_Observed), _name(_SelfJudged))
    truths = register().model_copy(update={"observations": declared})
    found = audit_observations([_Observed, _SelfJudged], truths)
    assert found == (f"{_name(_SelfJudged)}.verified",)


def test_a_verdict_without_its_policy_digest_or_observation_digest_is_refused() -> None:
    for missing in ("policy_revision", "evidence_digest", "judged_at"):
        fields = _verdict()
        fields.pop(missing)
        with pytest.raises(ValidationError):
            Verdict.model_validate(fields)
    for empty in ("policy_revision", "evidence_digest"):
        with pytest.raises(ValidationError):
            Verdict.model_validate(_verdict(**{empty: ""}))
    unjudged = Verdict.model_validate(_verdict(outcome="unknown", evidence_digest=""))
    assert unjudged.evidence_digest == "", "a verdict that judged nothing names no evidence"


def test_a_verdict_is_recomputed_offline_from_its_pinned_policy_and_observation(
    tmp_path: Path,
) -> None:
    (tmp_path / "rule.rego").write_text("package runs\n", encoding="utf-8")
    evidence = _Observed(rows=3)
    fields = _verdict(policy_revision=policy_revision(tmp_path), evidence_digest=digest(evidence))
    verdict = Verdict.model_construct(_fields_set=None, **fields)
    assert recompute(verdict, tmp_path, evidence)
    assert not recompute(verdict, tmp_path, _Observed(rows=4))
    (tmp_path / "rule.rego").write_text("package runs\nx := 1\n", encoding="utf-8")
    assert not recompute(verdict, tmp_path, evidence)


def test_completion_read_from_an_observation_is_refused() -> None:
    with pytest.raises(TypeError):
        completed("A.221", _Observed(rows=3))
