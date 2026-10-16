"""Another repository is read at a pinned commit, never at a moving branch (A.28).

A port reads its upstream at the exact commit it names. upstream:checkout clones blobless into
evidence, checks the commit out detached and verifies HEAD; an abbreviated SHA and a commit the
repository does not hold are refused. The fixture is a scratch repository with two commits.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

import upstream


def _repository(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "origin"
    repo.mkdir()

    def git(*args: str) -> str:
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        return done.stdout.strip()

    git("init", "--quiet", "--initial-branch=main")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    git("config", "commit.gpgsign", "false")
    (repo / "a.txt").write_text("first\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "--quiet", "-m", "first")
    first = git("rev-parse", "HEAD")
    (repo / "a.txt").write_text("second\n", encoding="utf-8")
    git("commit", "--quiet", "-am", "second")
    return repo, first, git("rev-parse", "HEAD")


def test_another_repository_is_checked_out_at_a_pinned_commit(tmp_path: Path) -> None:
    repo, first, _ = _repository(tmp_path)
    target = upstream.checkout(str(repo), first, tmp_path / "upstream")
    assert (target / "a.txt").read_text(encoding="utf-8") == "first\n"


def test_an_abbreviated_commit_is_refused(tmp_path: Path) -> None:
    repo, first, _ = _repository(tmp_path)
    with pytest.raises(SystemExit, match=re.escape("a full 40-character SHA")):
        upstream.checkout(str(repo), first[:12], tmp_path / "upstream")


def test_a_commit_not_in_the_repository_is_refused(tmp_path: Path) -> None:
    repo, _, _ = _repository(tmp_path)
    with pytest.raises(SystemExit, match=re.escape("is not in")):
        upstream.checkout(str(repo), "0" * 40, tmp_path / "upstream")
