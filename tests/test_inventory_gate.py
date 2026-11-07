"""centralization:inventory runs as a CI gate on every pull request (A.250).

A.249 merged a task the hub lacked, task:plan:resolve, and no gate noticed: the inventory
that refuses an unclassified capability ran only when someone ran it. A downstream checks
itself against the canonical hub in its own pull-request CI, always on, so this one does.
"""

from __future__ import annotations

from check_all import GATES


def test_the_inventory_is_a_ci_gate() -> None:
    """A gate runs scripts/centralization.py, and CI runs that gate on every pull request."""
    found = [gate for gate in GATES if gate.command[-1:] == ("scripts/centralization.py",)]
    assert found, [gate.name for gate in GATES]
    assert all(gate.runs_in_ci for gate in found), found
