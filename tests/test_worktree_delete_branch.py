# tests/test_worktree_delete_branch.py
"""worktree:remove deletes a branch only once origin/develop contains it (A.138, cscie103 D.229).

git branch -d judges a branch that has an upstream against that upstream, so for a pushed branch
it proves a push, never a merge. A branch develop does not contain is kept, and the reader is
sent to branches:retire (D.228), never to git branch -D.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import worktree


def _fake(monkeypatch: pytest.MonkeyPatch, ancestor: int) -> list[tuple[str, ...]]:
    """Every git call answered 0, except merge-base, which answers `ancestor`."""
    calls: list[tuple[str, ...]] = []

    def git_run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        code = ancestor if args[0] == "merge-base" else 0
        return subprocess.CompletedProcess([], code, "", "")

    monkeypatch.setattr(worktree, "git_run", git_run)
    return calls


def test_a_branch_develop_does_not_contain_is_kept(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _fake(monkeypatch, ancestor=1)
    assert worktree._delete_branch("feature/x") == 1
    assert [call for call in calls if call[:2] == ("branch", "-d")] == [], calls
    err = capsys.readouterr().err
    assert "does not contain it" in err and "branches:retire" in err, err


def test_a_branch_develop_contains_is_deleted(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake(monkeypatch, ancestor=0)
    assert worktree._delete_branch("feature/x") == 0
    assert calls[0][:2] == ("merge-base", "--is-ancestor"), calls
    assert ("branch", "-d", "feature/x") in calls, calls
