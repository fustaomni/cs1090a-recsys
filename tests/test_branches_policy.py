"""Each machine.branches guard, judged through its policy alone (A.101).

sync asks machine.branches after its updates, through opa.denials. cscie103 proves that whole
flow end to end; each proof here builds one repository state, flips one branch's position, and
asks the policy directly, so every guard has a proof that fails when that guard is removed.
"""

from __future__ import annotations

from opa import denials

ENTRYPOINT = "data.machine.branches.deny"


def _state(position: str) -> dict[str, object]:
    branch = {"name": "main", "position": position}
    return {"repository_state": {"branches": [branch], "long_lived": ["develop", "main"]}}


def _codes(payload: dict[str, object]) -> str:
    return " ".join(denials(ENTRYPOINT, payload))


def test_an_unobserved_state_is_refused_by_the_policy() -> None:
    assert "ERR_BRANCH_UNOBSERVED" in _codes({})
    assert "ERR_BRANCH_UNOBSERVED" not in _codes(_state("in_sync"))


def test_a_long_lived_branch_behind_is_refused_by_the_policy() -> None:
    assert "ERR_BRANCH_BEHIND" in _codes(_state("behind"))
    assert "ERR_BRANCH_BEHIND" not in _codes(_state("in_sync"))


def test_a_long_lived_branch_ahead_is_refused_by_the_policy() -> None:
    assert "ERR_BRANCH_AHEAD" in _codes(_state("ahead"))
    assert "ERR_BRANCH_AHEAD" not in _codes(_state("in_sync"))


def test_a_long_lived_branch_diverged_is_refused_by_the_policy() -> None:
    assert "ERR_BRANCH_DIVERGED" in _codes(_state("diverged"))
    assert "ERR_BRANCH_DIVERGED" not in _codes(_state("in_sync"))
