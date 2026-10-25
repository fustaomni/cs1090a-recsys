"""A sibling merge stages what its resolution names, and nothing is left behind (A.214).

A resolution can edit, delete or create files the merge itself never conflicted on. Each one
the resolution names with include is staged into the merge; a new file not named is refused,
since git would leave it out unseen; an include with no change behind it is refused; and the
merge commit runs in the cleaned environment, so the clone's hooks never see the caller's
virtual environment.
"""

from __future__ import annotations

import importlib
import inspect
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _commit(repo: Path, name: str, text: str, message: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "--quiet", "-m", message)


def _resolving(tmp_path: Path) -> tuple[ModuleType, object, Path, Path]:
    """A merge stopped on f.txt and resolved there; notes.txt and old.txt merged cleanly."""
    subject = importlib.import_module("sibling_checkout")
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    _commit(source, "mise.toml", "[tools]\n", "config")
    _commit(source, "f.txt", "base\n", "base")
    _commit(source, "notes.txt", "notes\n", "notes")
    _commit(source, "old.txt", "old\n", "old")
    sibling = subject.Sibling(name="demo", source=str(source), tools={"uv": "0.12.22"})
    parent = tmp_path / "siblings"
    clone = subject.checkout(sibling, parent)
    _git(clone, "config", "user.name", "t")
    _git(clone, "config", "user.email", "t@example.invalid")
    _git(clone, "switch", "--quiet", "-c", "feature/wip")
    _commit(clone, "f.txt", "ours\n", "ours")
    _commit(source, "f.txt", "theirs\n", "theirs")
    with pytest.raises(SystemExit):
        subject.refresh(sibling, parent, "D.1", trust=lambda _: 0)
    (clone / "f.txt").write_text("resolved\n", encoding="utf-8")
    return subject, sibling, parent, clone


def _takes_include(subject: ModuleType) -> None:
    parameters = inspect.signature(subject.conclude).parameters
    assert "include" in parameters, "conclude cannot be told which paths a resolution changed"


def test_included_paths_are_staged_into_the_merge(tmp_path: Path) -> None:
    """A modified, a deleted and a new file, each named, all land in the merge commit."""
    subject, sibling, parent, clone = _resolving(tmp_path)
    _takes_include(subject)
    (clone / "notes.txt").write_text("edited\n", encoding="utf-8")
    (clone / "old.txt").unlink()
    (clone / "new.txt").write_text("new\n", encoding="utf-8")
    included = ("notes.txt", "old.txt", "new.txt")
    subject.conclude(
        sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0, include=included
    )
    tree = _git(clone, "ls-tree", "--name-only", "HEAD").split()
    assert "new.txt" in tree and "old.txt" not in tree, tree
    assert _git(clone, "show", "HEAD:notes.txt") == "edited", "the edit was left out"


def test_an_untracked_file_left_out_is_refused(tmp_path: Path) -> None:
    """A new file the resolution did not name is refused by name, and HEAD does not move."""
    subject, sibling, parent, clone = _resolving(tmp_path)
    (clone / "new.txt").write_text("new\n", encoding="utf-8")
    before = _git(clone, "rev-parse", "HEAD")
    with pytest.raises(SystemExit) as refused:
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    assert "new.txt" in str(refused.value), refused.value
    assert _git(clone, "rev-parse", "HEAD") == before, "a merge leaving new.txt out was committed"


def test_an_include_naming_an_unchanged_path_is_refused(tmp_path: Path) -> None:
    """Naming a path with no change behind it is refused by name."""
    subject, sibling, parent, _ = _resolving(tmp_path)
    _takes_include(subject)
    with pytest.raises(SystemExit) as refused:
        subject.conclude(
            sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0, include=("notes.txt",)
        )
    assert "notes.txt" in str(refused.value), refused.value


def test_the_merge_commit_runs_without_the_callers_virtual_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The clone's commit-msg hook sees no VIRTUAL_ENV, though the caller has one."""
    subject, sibling, parent, clone = _resolving(tmp_path)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    seen = clone / ".git" / "venv-seen"
    hook = hooks / "commit-msg"
    hook.write_text(f'#!/bin/sh\nprintf "%s" "$VIRTUAL_ENV" > "{seen}"\n', encoding="utf-8")
    hook.chmod(0o755)
    _git(clone, "config", "core.hooksPath", str(hooks))
    monkeypatch.setenv("VIRTUAL_ENV", "/caller/venv")
    subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    assert seen.exists(), "the clone's commit-msg hook did not run"
    assert seen.read_text(encoding="utf-8") == "", seen.read_text(encoding="utf-8")
