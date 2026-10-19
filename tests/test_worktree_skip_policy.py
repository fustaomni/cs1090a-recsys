"""runs.worktree_skip's guards no real stopped rebase reaches, judged by the policy alone (A.127).

A rebase always records the commit it stopped on, and the task always supplies a plan, so the
absent input and the missing stopped commit are proven by asking the policy directly, as A.120
proves runs.worktree_continue's input guard. A complete, valid plan draws no denial at all.
"""

from __future__ import annotations

from opa import denials

ENTRYPOINT = "data.runs.worktree_skip.deny"
PLAN: dict[str, object] = {
    "operation": "rebase",
    "stopped": "a" * 40,
    "rebasing": "refs/heads/feature",
    "preserving": "refs/heads/keep",
    "preserved": True,
    "reason": "superseded by main",
}


def test_an_absent_plan_is_refused_by_the_policy() -> None:
    assert "ERR_SKIP_INPUT_MISSING" in " ".join(denials(ENTRYPOINT, {}))
    assert denials(ENTRYPOINT, {"worktree_skip": PLAN}) == []


def test_a_rebase_with_no_stopped_commit_is_refused_by_the_policy() -> None:
    plan = {**PLAN, "stopped": ""}
    assert "ERR_SKIP_NO_STOPPED" in " ".join(denials(ENTRYPOINT, {"worktree_skip": plan}))
