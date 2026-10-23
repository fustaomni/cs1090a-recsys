# tests/test_worktree_skip.py
"""A stopped rebase drops a commit only when another named ref preserves it (A.127).

A REAL STOPPED REBASE, BUILT LOCALLY as test_worktree_continue.py builds one: main and feature
change the same line, and feature is rebased onto main. With `keep`, a second branch holds
feature's commit first, so skipping it loses nothing. Each refusal is asserted by its code.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rebase_skip import skip_rebase
from rebase_state import conflicts


@pytest.fixture(autouse=True)
def _bare_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """No global git config, as on a bare CI runner: the tests must not depend on the user's."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))


def _git(repo: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "merge.conflictStyle", "merge")
    _git(tmp_path, "config", "user.useConfigOnly", "true")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    (tmp_path / "f.txt").write_text("line1\nshared\nline3\n", encoding="utf-8")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _stopped(tmp_path: Path, *, keep: bool) -> Path:
    """feature is rebased onto main and stops; with keep, `keep` holds feature's commit."""
    repo = _repository(tmp_path)
    _git(repo, "switch", "-q", "-c", "feature")
    (repo / "f.txt").write_text("line1\nfeature\nline3\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "feature change")
    if keep:
        _git(repo, "branch", "keep")
    _git(repo, "switch", "-q", "main")
    (repo / "f.txt").write_text("line1\nmain\nline3\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "main change")
    _git(repo, "switch", "-q", "feature")
    _git(repo, "rebase", "main", check=False)
    return repo


def test_a_preserved_commit_is_skipped_and_the_rebase_finishes(tmp_path: Path) -> None:
    repo = _stopped(tmp_path, keep=True)
    result = skip_rebase(repo, "keep", "superseded by main")
    assert result.outcome == "finished", result.message
    assert conflicts(repo).operation == "none"
    assert (repo / "f.txt").read_text(encoding="utf-8") == "line1\nmain\nline3\n"
    assert _git(repo, "log", "-1", "--format=%s", "keep") == "feature change"


def test_an_unpreserved_commit_is_refused(tmp_path: Path) -> None:
    repo = _stopped(tmp_path, keep=False)
    result = skip_rebase(repo, "main", "superseded by main")
    assert result.outcome == "refused"
    assert "ERR_SKIP_UNPRESERVED" in result.message, result.message
    assert conflicts(repo).operation == "rebase"


def test_the_rebasing_branch_cannot_preserve_its_own_commit(tmp_path: Path) -> None:
    repo = _stopped(tmp_path, keep=False)
    result = skip_rebase(repo, "feature", "superseded by main")
    assert result.outcome == "refused"
    assert "ERR_SKIP_SAME_BRANCH" in result.message, result.message
    assert conflicts(repo).operation == "rebase"


def test_a_skip_without_a_reason_is_refused(tmp_path: Path) -> None:
    repo = _stopped(tmp_path, keep=True)
    result = skip_rebase(repo, "keep", "   ")
    assert result.outcome == "refused"
    assert "ERR_SKIP_NO_REASON" in result.message, result.message
    assert conflicts(repo).operation == "rebase"


def test_skip_without_a_rebase_is_refused(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    _git(repo, "branch", "keep")
    result = skip_rebase(repo, "keep", "superseded by main")
    assert result.outcome == "refused"
    assert "ERR_SKIP_NO_REBASE" in result.message, result.message


def test_the_conflicting_file_holds_three_lines(tmp_path: Path) -> None:
    """The fixture is the multi-line file the docstring names, never one line of escape text."""
    repo = _repository(tmp_path)
    lines = (repo / "f.txt").read_text(encoding="utf-8").splitlines()
    assert lines == ["line1", "shared", "line3"], lines
