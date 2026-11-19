# tests/test_commit_merge.py
"""commit concludes a held merge, naming its paths and its plan step (D.360).

D.343 made every commit pass its named paths as a pathspec, and git refuses a pathspec while
MERGE_HEAD exists: "cannot do a partial commit during a merge". So a refresh stopped on a
conflict could no longer be concluded. While a merge is held, commit still refuses a staged path
it was not given, then commits the index itself, which is then exactly the named paths. These
run real git in a scratch repository, as D.343's proofs do.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from commit import execute_commit

BRANCH = "feature/scratch"
CONCLUDE = "chore(merge): conclude the scratch merge\n\nPlan-Step: D.360"


def _git(repo: Path, *argv: str) -> str:
    done = subprocess.run(["git", *argv], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout


def _runner(repo: Path) -> Callable[[list[str]], tuple[int, str]]:
    """The real boundary as run_git reports it: stdout on success, stderr on failure."""

    def run(argv: list[str]) -> tuple[int, str]:
        done = subprocess.run(["git", *argv], cwd=repo, capture_output=True, text=True, check=False)
        return done.returncode, (done.stdout if done.returncode == 0 else done.stderr).strip()

    return run


def _scratch(tmp_path: Path) -> Path:
    """An empty repository on the feature branch; no signing, no hooks."""
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
    return repo


def _write(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")


def _held_merge(tmp_path: Path) -> Path:
    """develop merged into the branch, stopped on plan.txt with lock.txt staged, then resolved."""
    repo = _scratch(tmp_path)
    _write(repo, "plan.txt", "base\n")
    _git(repo, "add", "plan.txt")
    _git(repo, "commit", "-q", "-m", "chore(scratch): base")
    _git(repo, "branch", "develop")
    _write(repo, "plan.txt", "ours\n")
    _git(repo, "commit", "-q", "-am", "chore(scratch): ours")
    _git(repo, "switch", "-q", "develop")
    _write(repo, "plan.txt", "theirs\n")
    _write(repo, "lock.txt", "raised\n")
    _git(repo, "add", "plan.txt", "lock.txt")
    _git(repo, "commit", "-q", "-m", "chore(scratch): theirs")
    _git(repo, "switch", "-q", BRANCH)
    stopped = subprocess.run(
        ["git", "merge", "--no-ff", "develop"], cwd=repo, capture_output=True, text=True
    )
    assert stopped.returncode != 0, stopped.stdout
    _write(repo, "plan.txt", "ours\ntheirs\n")
    return repo


def _held(repo: Path) -> bool:
    asked = ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"]
    return subprocess.run(asked, cwd=repo, capture_output=True, text=True).returncode == 0


def test_a_held_merge_concludes_as_a_merge_commit_with_its_plan_step(tmp_path: Path) -> None:
    """D.360: the resolved merge is committed whole, with two parents and its Plan-Step."""
    repo = _held_merge(tmp_path)
    outcome = execute_commit(
        BRANCH, CONCLUDE, ("lock.txt", "plan.txt"), git=_runner(repo), root=repo
    )
    assert (outcome.outcome, outcome.code) == ("success", "committed"), outcome
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()
    assert len(parents) == 3, parents
    assert "Plan-Step: D.360" in _git(repo, "log", "-1", "--format=%B")
    assert not _held(repo)


def test_a_held_merge_with_an_unnamed_staged_path_is_refused(tmp_path: Path) -> None:
    """D.360: mid-merge, a staged path the commit was not given is still refused by name."""
    repo = _held_merge(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    outcome = execute_commit(BRANCH, CONCLUDE, ("plan.txt",), git=_runner(repo), root=repo)
    assert (outcome.outcome, outcome.code) == ("refused", "staged_unnamed"), outcome
    assert "lock.txt" in outcome.message
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _held(repo)


def test_an_ordinary_commit_still_commits_only_its_named_paths(tmp_path: Path) -> None:
    """D.360: outside a merge nothing changes; a modified file that was not named stays out."""
    repo = _scratch(tmp_path)
    for name in ("named.txt", "other.txt"):
        _write(repo, name, "first\n")
    _git(repo, "add", "named.txt", "other.txt")
    _git(repo, "commit", "-q", "-m", "chore(scratch): add")
    for name in ("named.txt", "other.txt"):
        _write(repo, name, "second\n")
    outcome = execute_commit(
        BRANCH, "chore(scratch): named only", ("named.txt",), git=_runner(repo), root=repo
    )
    assert (outcome.outcome, outcome.code) == ("success", "committed"), outcome
    changed = _git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert changed == ["named.txt"], changed
    assert _git(repo, "status", "--porcelain").split() == ["M", "other.txt"]


def test_a_held_merge_refusal_says_to_name_the_merged_paths(tmp_path: Path) -> None:
    """D.371: mid-merge the remedy is to name the merged paths too, never to unstage them."""
    repo = _held_merge(tmp_path)
    outcome = execute_commit(BRANCH, CONCLUDE, ("plan.txt",), git=_runner(repo), root=repo)
    assert (outcome.outcome, outcome.code) == ("refused", "staged_unnamed"), outcome
    assert (outcome.data["held"], outcome.data["remedy"]) == (True, "name"), outcome
    assert "commit:unstage" not in outcome.message, outcome.message


def test_an_unnamed_path_outside_a_merge_is_still_told_to_unstage(tmp_path: Path) -> None:
    """D.371: outside a merge the remedy is unchanged: unstage what someone else staged."""
    repo = _scratch(tmp_path)
    _write(repo, "named.txt", "first\n")
    _git(repo, "add", "named.txt")
    _git(repo, "commit", "-q", "-m", "chore(scratch): add")
    _write(repo, "named.txt", "second\n")
    _write(repo, "stray.txt", "staged by someone else\n")
    _git(repo, "add", "stray.txt")
    outcome = execute_commit(
        BRANCH, "chore(scratch): named only", ("named.txt",), git=_runner(repo), root=repo
    )
    assert (outcome.outcome, outcome.code) == ("refused", "staged_unnamed"), outcome
    assert (outcome.data["held"], outcome.data["remedy"]) == (False, "unstage"), outcome
    assert "commit:unstage" in outcome.message, outcome.message
