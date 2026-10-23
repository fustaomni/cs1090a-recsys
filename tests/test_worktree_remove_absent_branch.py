# tests/test_worktree_remove_absent_branch.py
"""A present worktree whose feature branch is already gone is removed, and reported so (A.139).

The absent-worktree path asked rev-parse before deleting a branch; the present path did not, so a
worktree holding another branch, such as develop, was removed and then misreported as kept, with
merge-base asked about a branch that did not exist.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import worktree


def test_a_present_worktree_whose_branch_is_gone_is_removed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[str, ...]] = []

    def git_run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        code = 1 if args[:3] == ("rev-parse", "--verify", "--quiet") else 0
        return subprocess.CompletedProcess([], code, "", "")

    monkeypatch.setattr(worktree, "sibling_path", lambda slug: tmp_path)
    monkeypatch.setattr(worktree, "git_run", git_run)
    monkeypatch.setattr(worktree, "_git", lambda *args, **kwargs: "")
    assert worktree.cmd_remove("probe") == 0
    assert [call[0] for call in calls if call[0] in ("merge-base", "branch")] == [], calls
    assert "branch feature/probe already deleted" in capsys.readouterr().out
