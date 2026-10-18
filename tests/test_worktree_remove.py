# tests/test_worktree_remove.py
"""Removing an already-removed worktree succeeds, and never forces an unmerged branch (D.105).

remove refused with "does not exist" when the worktree was already gone, so a chain removing
after a sync broke although the end state it wanted already held. An absent worktree now has its
stale registration pruned (git worktree prune touches only entries whose directories are
missing), and its branch, if any, is deleted exactly as a present worktree's is: branch -d,
which refuses an unmerged branch. Nothing is ever forced.

THE FIRST TESTS OF REMOVE. git is faked throughout, so nothing is removed or deleted.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import worktree
from nonvacuous import nonempty

BRANCH = "feature/probe"


def _setup(
    monkeypatch: pytest.MonkeyPatch, path: Path, branch_exists: bool, delete_code: int = 0
) -> list[tuple[str, ...]]:
    """Fake every git call remove makes; return them all, in order."""
    calls: list[tuple[str, ...]] = []

    def git_run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:3] == ("rev-parse", "--verify", "--quiet"):
            return subprocess.CompletedProcess([], 0 if branch_exists else 1, "", "")
        if args[:2] == ("branch", "-d"):
            return subprocess.CompletedProcess([], delete_code, "", "not fully merged")
        return subprocess.CompletedProcess([], 0, "", "")

    def git(*args: str, **_: object) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(worktree, "sibling_path", lambda slug: path)
    monkeypatch.setattr(worktree, "git_run", git_run)
    monkeypatch.setattr(worktree, "_git", git)
    return calls


def _forced(calls: list[tuple[str, ...]]) -> bool:
    return any("-D" in call or "--force" in call or "-f" in call for call in calls)


def test_an_absent_worktree_with_no_branch_is_already_removed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The end state already holds: success, after pruning any stale registration."""
    calls = _setup(monkeypatch, tmp_path / "gone", branch_exists=False)
    assert worktree.cmd_remove("probe") == 0
    assert ("worktree", "prune") in calls, calls
    assert not any(call[:2] == ("branch", "-d") for call in nonempty(calls)), calls


def test_an_absent_worktree_whose_branch_remains_has_it_deleted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _setup(monkeypatch, tmp_path / "gone", branch_exists=True)
    assert worktree.cmd_remove("probe") == 0
    assert ("branch", "-d", BRANCH) in calls, calls


def test_an_unmerged_branch_is_never_forced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """branch -d refuses unmerged work; remove reports that, and never escalates to -D."""
    calls = _setup(monkeypatch, tmp_path / "gone", branch_exists=True, delete_code=1)
    assert worktree.cmd_remove("probe") == 1
    assert not _forced(calls), calls


def test_a_present_worktree_is_removed_as_before(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _setup(monkeypatch, tmp_path, branch_exists=True)
    assert worktree.cmd_remove("probe") == 0
    assert ("worktree", "remove", str(tmp_path)) in calls, calls
    assert ("branch", "-d", BRANCH) in calls, calls
