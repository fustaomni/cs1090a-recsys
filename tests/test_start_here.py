# tests/test_start_here.py
"""start:here cuts a branch that tracks nothing, so a bare push never reaches develop (A.131).

A branch started from a remote-tracking ref inherits it as its upstream under git's default
branch.autosetupmerge, and a plain `git push` then publishes there: a 2026 report shows feature
commits landing on a shared dev branch with no review. worktree:add cuts with --no-track (A.93).
start:here PRINTS the command a shell evaluates, so this proof evaluates exactly that command in
a real clone, offline, and asks git whether the new branch has an upstream.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _bare_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """No global git config, as on a bare CI runner: the proof must not depend on the user's."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def _printed(slug: str) -> str:
    """The command start:here prints, from its own run script, with the variable mise sets."""
    tasks = tomllib.loads((REPO / "mise.toml").read_text(encoding="utf-8"))["tasks"]
    script = str(tasks["start:here"]["run"])
    shown = subprocess.run(
        ["bash", "-c", script],
        env={**os.environ, "usage_slug": slug},
        capture_output=True,
        text=True,
        check=True,
    )
    return shown.stdout.strip()


def _clone(tmp_path: Path) -> Path:
    """A clone of a local origin whose develop holds one commit."""
    origin, seed, clone = tmp_path / "origin.git", tmp_path / "seed", tmp_path / "clone"
    _git(tmp_path, "init", "-q", "--bare", "-b", "develop", str(origin))
    _git(tmp_path, "init", "-q", "-b", "develop", str(seed))
    (seed / "f.txt").write_text("base\\n", encoding="utf-8")
    _git(seed, "add", "f.txt")
    _git(seed, "commit", "-q", "-m", "base")
    _git(seed, "push", "-q", str(origin), "develop")
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    return clone


def test_start_here_cuts_a_branch_with_no_upstream(tmp_path: Path) -> None:
    clone = _clone(tmp_path)
    cut = subprocess.run(
        ["bash", "-c", _printed("probe")], cwd=clone, capture_output=True, text=True, check=False
    )
    assert cut.returncode == 0, cut.stderr
    assert _git(clone, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "feature/probe"
    found = _git(clone, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
    assert found.returncode != 0, f"feature/probe tracks {found.stdout.strip()}"
