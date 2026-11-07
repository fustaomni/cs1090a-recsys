# tests/test_status_paths.py
"""status:paths prints every changed path a commit should name, derived rather than recalled
(D.355, ported from cs1090a-recsys's `commit paths`, RS.30).

recsys built it after a commit's path list, composed from memory, was wrong six times in one
session. Two traps shaped it, both proven here: git collapses a wholly untracked directory to
one entry unless asked for every file, and with -z a rename is two records, which a reader that
treats every record alike shifts by one.

ADAPTED: BOTH SIDES OF A RENAME. recsys drops the source path, since its commit stages with git
add. This hub's commit refuses a staged path it was not given (D.343), and a staged rename stages
the source's deletion, so the list a commit here should name holds both.

Each proof works in its own scratch repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import spine
import status_paths
from command_outcome import CommandOutcome

IDENTITY = ["-c", "user.name=proof", "-c", "user.email=proof"]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *IDENTITY, *args], cwd=root, check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    """One committed file and an ignore rule, on develop."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--quiet", "-b", "develop")
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    _git(root, "add", "--", "a.txt", ".gitignore")
    _git(root, "commit", "--quiet", "-m", "first")
    return root


def _named(root: Path, capsys: pytest.CaptureFixture[str]) -> list[str]:
    assert status_paths.main(root=root) == 0
    outcome = CommandOutcome.model_validate_json(capsys.readouterr().out)
    paths = outcome.data["paths"]
    assert isinstance(paths, list), outcome
    return [str(path) for path in paths]


def test_a_file_in_a_new_directory_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """By its own path: the file a commit is most likely to forget is never a bare folder."""
    root = _repo(tmp_path)
    (root / "pkg" / "deep").mkdir(parents=True)
    (root / "pkg" / "deep" / "m.py").write_text("x = 1\n", encoding="utf-8")
    assert _named(root, capsys) == ["pkg/deep/m.py"]


def test_a_rename_names_both_its_sides(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Both whole paths, neither shifted by the rename's second record."""
    root = _repo(tmp_path)
    _git(root, "mv", "a.txt", "renamed.txt")
    assert _named(root, capsys) == ["a.txt", "renamed.txt"]


def test_an_ignored_file_is_not_named(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """What git ignores is never a path a commit should name."""
    root = _repo(tmp_path)
    (root / "ignored").mkdir()
    (root / "ignored" / "x.txt").write_text("x\n", encoding="utf-8")
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    assert _named(root, capsys) == ["a.txt"]


def test_a_clean_tree_names_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Nothing changed is an answer, and the task still succeeds."""
    assert _named(_repo(tmp_path), capsys) == []


def test_an_absent_request_is_refused_by_the_policy() -> None:
    """runs.status_paths refuses when no observation is supplied, never reading it as clean."""
    evidence = status_paths.StatusPaths(answered=True, detail="", paths=())
    found = spine.evaluate(
        evidence, "not_status_paths", status_paths.POLICY, status_paths.ENTRYPOINT
    )
    codes = {rule.code for rule in found.rules if rule.outcome == "fail"}
    assert "ERR_STATUS_PATHS_INPUT_MISSING" in codes, found


def test_outside_a_repository_is_refused_not_read_as_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A git that cannot answer is never an empty list: the run is refused by its code."""
    assert status_paths.main(root=tmp_path) == 2
    outcome = CommandOutcome.model_validate_json(capsys.readouterr().out)
    assert outcome.outcome == "refused", outcome
    assert "ERR_STATUS_PATHS_UNANSWERED" in outcome.message, outcome
