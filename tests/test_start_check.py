# tests/test_start_check.py
"""The branch guard refuses protected branches, except a repository's root commit (F6d).

start:check read the branch with `git rev-parse --abbrev-ref HEAD` under `set -e`, which fails
before a repository's first commit, so the guard crashed (exit 128) instead of deciding. The
root commit is the one commit that cannot be made anywhere else -- no branch can be cut from a
main with no commit -- so it is allowed, once, and said so. The guard runs from its own text in
mise.toml, in scratch repositories.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from gitenv import scrubbed_env

ROOT = Path(__file__).resolve().parent.parent
IDENTITY = (
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@example.invalid",
    "-c",
    "commit.gpgsign=false",
)


def _guard_text() -> str:
    tasks = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))["tasks"]
    text = tasks["start:check"]["run"]
    assert isinstance(text, str), text
    return text


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *IDENTITY, *args], cwd=repo, env=scrubbed_env(), check=True, capture_output=True
    )


def _guard(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", _guard_text()],
        cwd=repo,
        env=scrubbed_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_root_commit_on_main_is_allowed_and_says_so(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    run = _guard(tmp_path)
    assert run.returncode == 0, run.stderr
    assert "root commit" in run.stderr, run.stderr


def test_main_with_a_commit_is_refused(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "root")
    run = _guard(tmp_path)
    assert run.returncode == 1, run.stderr
    assert "refusing" in run.stderr, run.stderr


def test_a_feature_branch_is_allowed(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "feature/x")
    assert _guard(tmp_path).returncode == 0
