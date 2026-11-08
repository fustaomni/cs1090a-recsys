# tests/test_repo_state_prunable.py
"""A registered worktree whose directory is gone is reported prunable, never fatal (D.442).

A publication's snapshot is a detached worktree under the temporary directory. When the
machine running it ended mid-gate, the directory went with it while git kept the worktree
registered, and every later observation of the repository raised FileNotFoundError running
git status there. Git marks such a worktree prunable; the observer reads that, runs nothing
inside it, and leaves pruning to an explicit step.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from gitenv import git
from repo_report import observe
from repo_state import _worktrees

IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.invalid")


def test_a_worktree_whose_directory_is_gone_is_reported_prunable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git("init", "-q", "-b", "develop", cwd=repo)
    git(*IDENTITY, "commit", "-q", "--allow-empty", "-m", "start", cwd=repo)
    snapshot = tmp_path / "snapshot"
    git("worktree", "add", "-q", "--detach", str(snapshot), cwd=repo)
    shutil.rmtree(snapshot)
    found = {worktree.path.name: worktree for worktree in _worktrees(repo)}
    assert found["snapshot"].prunable, found
    assert not found["repo"].prunable, found


def test_the_report_names_a_vanished_worktree_and_counts_nothing_in_it(tmp_path: Path) -> None:
    """repo:state's observation returns, listing the vanished worktree, never reading inside it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git("init", "-q", "-b", "develop", cwd=repo)
    git(*IDENTITY, "commit", "-q", "--allow-empty", "-m", "start", cwd=repo)
    git("update-ref", "refs/remotes/origin/develop", "HEAD", cwd=repo)
    snapshot = tmp_path / "snapshot"
    git("worktree", "add", "-q", "--detach", str(snapshot), cwd=repo)
    shutil.rmtree(snapshot)
    report = observe(repo)
    assert [Path(path).name for path in report.prunable] == ["snapshot"], report
    assert [Path(worktree.path).name for worktree in report.worktrees] == ["repo"], report
