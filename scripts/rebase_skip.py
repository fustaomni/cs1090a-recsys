# scripts/rebase_skip.py
"""worktree:skip -- drop a stopped rebase's commit only when another ref preserves it (A.127).

cscie103's rebase_state.py at the pin reads conflicts and continues; it cannot drop a commit,
and a raw `git rebase --skip` discards one with nothing to say it survives anywhere else.
skip-plan/v1 observes the commit git stopped on (REBASE_HEAD), the branch being rebased
(rebase-merge/head-name), the named preserving ref, whether the stopped commit is its ancestor,
and the reason given. runs.worktree_skip judges that plan first; only then is the commit
skipped, through gitenv, and the result observed again: finished, or paused at the next.

THE BRANCH BEING REBASED NEVER PRESERVES ITS OWN COMMIT: its ref still points at the old tip
while the rebase runs, and moves past the commit the moment the rebase finishes.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from command_outcome import announce
from contract_base import Contract
from gitenv import git
from rebase_state import ConflictReport, Operation, conflicts
from spine import Decision, decide, enforce, evaluate, halted, reasons, refusal_code

ROOT = Path(__file__).resolve().parent.parent
SUBJECT = "worktree_skip"
POLICY = ROOT / "policies" / "runs" / "worktree_skip"
ENTRYPOINT = "data.runs.worktree_skip.deny"
COMMAND = "worktree:skip"
USAGE = "usage: mise run run worktree:skip <slug> <preserving-ref> <reason>"


class SkipPlan(Contract):
    """skip-plan/v1: what a skip would drop, and where it survives, observed before it acts."""

    contract: Literal["skip-plan/v1"] = "skip-plan/v1"
    operation: Operation
    stopped: str
    rebasing: str
    preserving: str
    preserved: bool
    reason: str


class SkipResult(Contract):
    outcome: Literal["finished", "paused", "refused", "failed"]
    message: str
    plan: SkipPlan
    after: ConflictReport
    decision: Decision


def _stopped(path: Path) -> str:
    found = git("rev-parse", "--verify", "--quiet", "REBASE_HEAD", cwd=path)
    return found.stdout.strip() if found.returncode == 0 else ""


def _rebasing(path: Path) -> str:
    located = git("rev-parse", "--git-path", "rebase-merge/head-name", cwd=path).stdout.strip()
    head_name = path / located
    if not located or not head_name.is_file():
        return ""
    return head_name.read_text(encoding="utf-8").strip()


def _resolved(path: Path, ref: str) -> str:
    found = git("rev-parse", "--verify", "--quiet", "--symbolic-full-name", ref, cwd=path)
    return found.stdout.strip() if found.returncode == 0 else ""


def _preserved(path: Path, stopped: str, preserving: str) -> bool:
    if not stopped or not preserving:
        return False
    return git("merge-base", "--is-ancestor", stopped, preserving, cwd=path).returncode == 0


def plan_skip(path: Path, ref: str, reason: str) -> SkipPlan:
    stopped = _stopped(path)
    preserving = _resolved(path, ref)
    return SkipPlan(
        operation=conflicts(path).operation,
        stopped=stopped,
        rebasing=_rebasing(path),
        preserving=preserving,
        preserved=_preserved(path, stopped, preserving),
        reason=reason,
    )


def _failed(path: Path, plan: SkipPlan, message: str) -> SkipResult:
    stopped = halted(SUBJECT, ENTRYPOINT, POLICY, message)
    return SkipResult(
        outcome="failed", message=message, plan=plan, after=conflicts(path), decision=stopped
    )


def skip_rebase(path: Path, ref: str, reason: str) -> SkipResult:
    """Drop the commit a rebase stopped on, only once policy finds it preserved by `ref`."""
    plan = plan_skip(path, ref, reason)
    found = evaluate(plan, SUBJECT, POLICY, ENTRYPOINT)
    decision = decide(found)
    if decision.action != "proceed":
        return SkipResult(
            outcome="refused",
            message=reasons(found),
            plan=plan,
            after=conflicts(path),
            decision=decision,
        )
    # THROUGH GITENV, its environment scrubbed; core.editor=true so no editor ever opens.
    skipped = git("-c", "core.editor=true", "rebase", "--skip", cwd=path)
    after = conflicts(path)
    if after.operation == "rebase" and after.files:
        message = "paused at the next conflicting commit"
        return SkipResult(
            outcome="paused", message=message, plan=plan, after=after, decision=decision
        )
    if skipped.returncode != 0 or after.operation != "none":
        detail = (skipped.stderr or skipped.stdout).strip() or "rebase did not finish"
        return _failed(path, plan, detail)
    return SkipResult(
        outcome="finished", message="rebase finished", plan=plan, after=after, decision=decision
    )


def main(argv: Sequence[str] | None = None) -> int:
    """worktree:skip <slug> <preserving-ref> <reason>."""
    from worktree import sibling_path

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, USAGE)
        return enforce(announce(COMMAND, stopped, "usage", USAGE, {}))
    slug, ref, reason = args
    path = sibling_path(slug)
    if not path.exists():
        missing = f"{path} does not exist"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, missing)
        return enforce(announce(COMMAND, stopped, "worktree_missing", missing, {}))
    result = skip_rebase(path, ref, reason)
    code = (
        refusal_code(result.decision, "skip_refused")
        if result.outcome == "refused"
        else f"skip_{result.outcome}"
    )
    data = result.model_dump(mode="json")
    return enforce(announce(COMMAND, result.decision, code, result.message, data))


if __name__ == "__main__":
    raise SystemExit(main())
