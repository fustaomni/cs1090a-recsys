# tests/test_start_switch.py
"""start:switch moves this shell's checkout to an existing branch, or refuses by name (A.140).

The main checkout belongs on develop, but a task runs in a subprocess and cannot change the
invoking shell's checkout, so, as start:here does, start:switch PRINTS the command the shell
evaluates. git allows a branch in one worktree only, so a branch another worktree holds is
refused before git would refuse it, as is one that does not exist. Each proof evaluates the
printed command in a real clone, offline.
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


def _clone(tmp_path: Path) -> Path:
    """A clone of a local origin whose develop holds one commit."""
    origin, seed, clone = tmp_path / "origin.git", tmp_path / "seed", tmp_path / "clone"
    _git(tmp_path, "init", "-q", "--bare", "-b", "develop", str(origin))
    _git(tmp_path, "init", "-q", "-b", "develop", str(seed))
    (seed / "f.txt").write_text("base\n", encoding="utf-8")
    _git(seed, "add", "f.txt")
    _git(seed, "commit", "-q", "-m", "base")
    _git(seed, "push", "-q", str(origin), "develop")
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    return clone


def _switch(clone: Path, branch: str) -> subprocess.CompletedProcess[str]:
    """Print start:switch's command in `clone`, as mise would, then evaluate it there."""
    tasks = tomllib.loads((REPO / "mise.toml").read_text(encoding="utf-8"))["tasks"]
    script = str(tasks["start:switch"]["run"])
    shown = subprocess.run(
        ["bash", "-c", script],
        cwd=clone,
        env={**os.environ, "usage_branch": branch},
        capture_output=True,
        text=True,
        check=True,
    )
    return subprocess.run(
        ["bash", "-c", shown.stdout.strip()], cwd=clone, capture_output=True, text=True, check=False
    )


def _head(clone: Path) -> str:
    return _git(clone, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def test_a_checkout_on_a_feature_branch_returns_to_develop(tmp_path: Path) -> None:
    clone = _clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "feature/old")
    moved = _switch(clone, "develop")
    assert moved.returncode == 0, moved.stderr
    assert _head(clone) == "develop"


def test_a_branch_another_worktree_holds_is_refused(tmp_path: Path) -> None:
    clone = _clone(tmp_path)
    _git(clone, "worktree", "add", "-q", "-b", "feature/held", str(tmp_path / "other"))
    refused = _switch(clone, "feature/held")
    assert refused.returncode != 0
    assert "checked out in another worktree" in refused.stderr, refused.stderr
    assert _head(clone) == "develop"


def test_a_branch_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    clone = _clone(tmp_path)
    refused = _switch(clone, "feature/nowhere")
    assert refused.returncode != 0
    assert "no local branch feature/nowhere" in refused.stderr, refused.stderr
    assert _head(clone) == "develop"
