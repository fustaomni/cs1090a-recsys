"""A branch is pushed only to its own ref, never a protected one, after the gate (A.91)."""

from __future__ import annotations

from pathlib import Path

import spine
from branch_push import ENTRYPOINT, POLICY, ROOT, SUBJECT, PushRequest, gate_passed_at
from command_outcome import CommandOutcome
from gitenv import git
from run_ledger import append

HEAD = "a" * 40
CHECK: dict[str, object] = {
    "command": "check",
    "outcome": "success",
    "code": "gates_passed",
    "message": "all gates passed",
    "data": {},
}


def _request(**fields: object) -> PushRequest:
    base: dict[str, object] = {
        "branch": "feature/probe",
        "remote_ref": "refs/heads/feature/probe",
        "head": HEAD,
        "protected": False,
        "gate_passed_at_head": True,
    }
    base.update(fields)
    return PushRequest.model_validate(base)


def _codes(request: PushRequest, subject: str = SUBJECT) -> set[str]:
    found = spine.evaluate(request, subject, POLICY, ENTRYPOINT)
    return {rule.code for rule in found.rules if rule.outcome == "fail"}


def test_a_feature_branch_with_its_gate_passed_may_be_pushed() -> None:
    assert _codes(_request()) == set()


def test_an_absent_request_is_refused_by_the_policy() -> None:
    assert "ERR_PUSH_INPUT_MISSING" in _codes(_request(), "not_branch_push")


def test_a_detached_head_is_refused() -> None:
    assert "ERR_PUSH_DETACHED" in _codes(_request(branch=None, remote_ref=None))


def test_a_protected_branch_is_refused() -> None:
    request = _request(branch="develop", remote_ref="refs/heads/develop", protected=True)
    assert "ERR_PUSH_PROTECTED_BRANCH" in _codes(request)


def test_a_push_without_the_gate_passed_is_refused() -> None:
    assert "ERR_PUSH_GATE_UNPROVEN" in _codes(_request(gate_passed_at_head=False))


def test_the_gate_is_read_from_the_ledger_at_this_head(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    head = git("rev-parse", "HEAD", cwd=ROOT).stdout.strip()
    assert not gate_passed_at(head, ledger)
    append(CommandOutcome.model_validate(CHECK), ledger=ledger, signer=None)
    assert gate_passed_at(head, ledger)
    assert not gate_passed_at("b" * 40, ledger)
