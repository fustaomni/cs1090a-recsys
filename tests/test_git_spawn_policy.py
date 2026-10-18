"""The git-spawn policy refuses an unobserved inventory and an empty scan by its own rules (A.89).

The audit's tests judge real scans, which always find files and always supply the inventory, so
neither rule could fail them. These proofs ask runs.git_spawns for each code directly.
"""

from __future__ import annotations

import spine
from git_spawn_audit import ENTRYPOINT, POLICY, SUBJECT, GitSpawnInventory


def _codes(inventory: GitSpawnInventory, subject: str = SUBJECT) -> set[str]:
    found = spine.evaluate(inventory, subject, POLICY, ENTRYPOINT)
    return {rule.code for rule in found.rules if rule.outcome == "fail"}


def test_an_unobserved_inventory_is_refused_by_the_policy() -> None:
    inventory = GitSpawnInventory(files_scanned=1, spawns=())
    assert "ERR_GIT_SPAWNS_INPUT_MISSING" in _codes(inventory, "not_git_spawns")


def test_an_empty_scan_is_refused_by_the_policy() -> None:
    inventory = GitSpawnInventory(files_scanned=0, spawns=())
    assert "ERR_GIT_SPAWNS_NOTHING_SCANNED" in _codes(inventory)
