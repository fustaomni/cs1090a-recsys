# tests/test_commit_unstage.py
"""commit refuses a staged path it was not given, and commit:unstage is the way out (D.343).

Ported from cs1090a-data-science and cs1090a-recsys, where the two are one capability: the
commit refusal names the task that unstages. These run real git in a scratch repository.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from commit import execute_commit

BRANCH = "feature/scratch"


def _git(repo: Path, *argv: str) -> str:
    done = subprocess.run(["git", *argv], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout


def _repo(tmp_path: Path) -> Path:
    """Two files committed, then both edited and staged; no signing, no hooks."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for argv in (
        ["init", "-q", "-b", BRANCH],
        ["config", "user.name", "zqx"],
        ["config", "user.email", "zqx"],
        ["config", "commit.gpgsign", "false"],
        ["config", "core.hooksPath", str(repo / ".no-hooks")],
    ):
        _git(repo, *argv)
    for name in ("named.txt", "stray.txt"):
        (repo / name).write_text("first\n", encoding="utf-8")
    _git(repo, "add", "named.txt", "stray.txt")
    _git(repo, "commit", "-q", "-m", "chore(scratch): add")
    for name in ("named.txt", "stray.txt"):
        (repo / name).write_text("second\n", encoding="utf-8")
    _git(repo, "add", "named.txt", "stray.txt")
    return repo


def _runner(repo: Path) -> Callable[[list[str]], tuple[int, str]]:
    """The real boundary as run_git reports it: stdout on success, stderr on failure."""

    def run(argv: list[str]) -> tuple[int, str]:
        done = subprocess.run(["git", *argv], cwd=repo, capture_output=True, text=True, check=False)
        return done.returncode, (done.stdout if done.returncode == 0 else done.stderr).strip()

    return run


def _staged(repo: Path) -> set[str]:
    return set(_git(repo, "diff", "--cached", "--name-only").split())


def test_unstage_clears_named_paths_and_keeps_their_bytes(tmp_path: Path) -> None:
    """D.343: only the named path leaves the index, and its file on disk is unchanged."""
    from commit import execute_unstage

    repo = _repo(tmp_path)
    outcome = execute_unstage(("stray.txt",), git=_runner(repo))
    assert (outcome.outcome, outcome.code) == ("success", "unstaged"), outcome
    assert _staged(repo) == {"named.txt"}
    assert (repo / "stray.txt").read_text(encoding="utf-8") == "second\n"


def test_unstage_refuses_a_named_path_that_is_not_staged(tmp_path: Path) -> None:
    """D.343: unstaging what is not staged is refused by name, never reported as done."""
    from commit import execute_unstage

    repo = _repo(tmp_path)
    _git(repo, "restore", "--staged", "stray.txt")
    outcome = execute_unstage(("stray.txt",), git=_runner(repo))
    assert (outcome.outcome, outcome.code) == ("refused", "not_staged"), outcome
    assert "stray.txt" in outcome.message
    assert _staged(repo) == {"named.txt"}


def test_commit_refuses_a_staged_path_it_was_not_given(tmp_path: Path) -> None:
    """D.343: a staged path the commit was not given is refused, naming commit:unstage."""
    repo = _repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    outcome = execute_commit(
        BRANCH, "chore(scratch): named only", ("named.txt",), git=_runner(repo), root=repo
    )
    assert (outcome.outcome, outcome.code) == ("refused", "staged_unnamed"), outcome
    assert "stray.txt" in outcome.message and "commit:unstage" in outcome.message
    assert _git(repo, "rev-parse", "HEAD") == head
