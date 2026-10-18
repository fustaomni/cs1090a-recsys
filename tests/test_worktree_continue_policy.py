"""runs.worktree_continue's input guard, judged through its policy alone (A.120).

cscie103 proves a remaining marker and a missing rebase end to end, through a stopped rebase.
No such path reaches the input guard, so it is proven here by asking the policy directly.
"""

from __future__ import annotations

from opa import denials

ENTRYPOINT = "data.runs.worktree_continue.deny"


def test_an_absent_plan_is_refused_by_the_policy() -> None:
    assert "ERR_CONTINUE_INPUT_MISSING" in " ".join(denials(ENTRYPOINT, {}))
    plan: dict[str, object] = {"worktree_continue": {"operation": "rebase", "with_markers": []}}
    assert "ERR_CONTINUE_INPUT_MISSING" not in " ".join(denials(ENTRYPOINT, plan))
