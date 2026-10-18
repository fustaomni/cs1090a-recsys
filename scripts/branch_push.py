"""branch:push -- a feature branch reaches GitHub only through this task (A.91).

A PUSH IS DECIDED BEFORE IT IS MADE. The task observes the current branch and derives the ref
it would write, always the same name under refs/heads, so a branch is never pushed onto another;
whether that ref is protected, since main and develop change only through a merged pull request;
and whether the full gate passed at this exact commit, read from an intact hash-chained ledger.
runs.branch_push decides. The push never forces: git itself refuses a non-fast-forward.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

import spine
from command_outcome import CommandOutcome
from contract_base import Contract
from gitenv import git
from run_ledger import RunRecord, default_ledger, verify

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "policies" / "runs" / "branch_push"
ENTRYPOINT = "data.runs.branch_push.deny"
SUBJECT = "branch_push"
PROTECTED = ("main", "develop")
REMOTE = "origin"


class PushRequest(Contract):
    """push-request/v1: the ref a push would write, and what decides whether it may."""

    contract: Literal["push-request/v1"] = "push-request/v1"
    branch: str | None
    remote_ref: str | None
    head: str
    protected: bool
    gate_passed_at_head: bool


def gate_passed_at(head: str, ledger: Path) -> bool:
    """Whether the newest full-gate run recorded at this commit passed, in an intact ledger."""
    if not ledger.exists() or not verify(ledger).intact:
        return False
    verdict: str | None = None
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = RunRecord.model_validate_json(line)
        if record.task == "check" and record.head == head:
            verdict = record.verdict
    return verdict == "pass"


def observe(root: Path, ledger: Path) -> PushRequest:
    """The push this checkout would make, as evidence for runs.branch_push."""
    named = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=root)
    branch = named.stdout.strip() if named.returncode == 0 else None
    head = git("rev-parse", "HEAD", cwd=root).stdout.strip()
    return PushRequest(
        branch=branch,
        remote_ref=f"refs/heads/{branch}" if branch is not None else None,
        head=head,
        protected=branch is not None and branch in PROTECTED,
        gate_passed_at_head=gate_passed_at(head, ledger),
    )


def _announce(outcome: str, code: str, message: str, data: dict[str, object]) -> int:
    envelope = CommandOutcome.model_validate(
        {
            "command": "branch:push",
            "outcome": outcome,
            "code": code,
            "message": message,
            "data": data,
        }
    )
    print(json.dumps(envelope.model_dump(), indent=2))
    return envelope.exit_code


def main() -> int:
    request = observe(ROOT, default_ledger())
    data: dict[str, object] = request.model_dump(mode="json")
    found = spine.evaluate(request, SUBJECT, POLICY, ENTRYPOINT)
    refusals = sorted(rule.code for rule in found.rules if rule.outcome == "fail")
    if refusals:
        return _announce("refused", "push_refused", ", ".join(refusals), data)
    pushed = git("push", REMOTE, f"refs/heads/{request.branch}:{request.remote_ref}", cwd=ROOT)
    if pushed.returncode != 0:
        raise SystemExit(f"git push failed: {pushed.stderr.strip()}")
    message = f"{request.branch} pushed to {REMOTE} at {request.head[:12]}"
    return _announce("success", "pushed", message, data)


if __name__ == "__main__":
    sys.exit(main())
