# tests/test_source_diff.py
"""source:diff shows a worktree's uncommitted changes as data before anything is discarded (D.476).

A dirty worktree is inspected before it is archived or restored. Each changed file is reported
with its hunks and the lines they add and remove; an untracked file is listed by name and size
and never read, so a stray secret is not copied into the report; a clean tree reports nothing;
and a slug that names no worktree is refused.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(autouse=True)
def _bare_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """No global git config, as on a bare CI runner."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    """One committed file; a repo-local identity, never a guessed one."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.useConfigOnly", "true")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    (tmp_path / "f.txt").write_text("a\nb\nc\n", encoding="utf-8")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _subject() -> ModuleType:
    module = importlib.import_module("source_diff")
    assert hasattr(module, "diff"), "source_diff has no diff"
    return module


def test_a_modified_file_reports_each_hunk_with_its_added_and_removed_lines(
    tmp_path: Path,
) -> None:
    """D.476: one line changed and one appended are two added lines and one removed."""
    repo = _repo(tmp_path)
    (repo / "f.txt").write_text("a\nB\nc\nd\n", encoding="utf-8")
    report = _subject().diff(repo)
    assert [changed.path for changed in report.files] == ["f.txt"], report
    changed = report.files[0]
    assert changed.status == "modified", changed
    assert sum(hunk.added for hunk in changed.hunks) == 2, changed
    assert sum(hunk.removed for hunk in changed.hunks) == 1, changed


def test_an_untracked_file_is_listed_without_being_read(tmp_path: Path) -> None:
    """D.476: an untracked file is named with its size, and its content appears nowhere."""
    repo = _repo(tmp_path)
    (repo / "new.txt").write_text("do-not-read-me", encoding="utf-8")
    report = _subject().diff(repo)
    assert [(entry.path, entry.size) for entry in report.untracked] == [("new.txt", 14)], report
    assert "do-not-read-me" not in report.model_dump_json(), report


def test_a_clean_worktree_reports_no_changes(tmp_path: Path) -> None:
    """D.476: with nothing changed there is nothing to report, and that is not an error."""
    report = _subject().diff(_repo(tmp_path))
    assert list(report.files) == [], report
    assert list(report.untracked) == [], report


def test_a_slug_naming_no_worktree_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D.476: a slug that names no worktree is refused, never read as an empty diff.

    HERMETIC: sibling_path asks git where the main checkout is, and a copy of the tree has no
    git, so the slug is mapped to a directory that does not exist under tmp_path instead.
    """

    def _absent(slug: str) -> Path:
        return tmp_path / f"absent-{slug}"

    monkeypatch.setattr("worktree.sibling_path", _absent)
    assert _subject().main(["no-such-worktree-d476"]) != 0
