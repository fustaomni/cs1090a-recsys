"""A sibling merge commit leaves nothing out (A.213).

A resolution can touch files the merge itself merged cleanly. Git commits only what is staged,
so a tracked file edited and left unstaged would be silently missing from the merge commit.
sibling:conclude refuses, naming every such file; a resolution staged in full concludes.
"""

from __future__ import annotations

import importlib
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
    """A merge stopped on f.txt and resolved there, with notes.txt and more.txt merged cleanly."""
    subject = importlib.import_module("sibling_checkout")
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    _commit(source, "mise.toml", "[tools]\n", "config")
    _commit(source, "f.txt", "base\n", "base")
    _commit(source, "notes.txt", "notes\n", "notes")
    _commit(source, "more.txt", "more\n", "more")
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


def test_an_unstaged_tracked_change_is_refused_and_nothing_committed(tmp_path: Path) -> None:
    """notes.txt edited during the resolution and left unstaged: refused by name, no commit."""
    subject, sibling, parent, clone = _resolving(tmp_path)
    (clone / "notes.txt").write_text("edited while resolving\n", encoding="utf-8")
    before = _git(clone, "rev-parse", "HEAD")
    with pytest.raises(SystemExit) as refused:
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    assert "notes.txt" in str(refused.value), refused.value
    assert _git(clone, "rev-parse", "HEAD") == before, "a merge leaving notes.txt out was committed"


def test_every_unstaged_path_is_named(tmp_path: Path) -> None:
    """Two unstaged edits are both named in the one refusal."""
    subject, sibling, parent, clone = _resolving(tmp_path)
    (clone / "notes.txt").write_text("edited\n", encoding="utf-8")
    (clone / "more.txt").write_text("edited\n", encoding="utf-8")
    with pytest.raises(SystemExit) as refused:
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    assert "notes.txt" in str(refused.value), refused.value
    assert "more.txt" in str(refused.value), refused.value


def test_a_fully_staged_resolution_is_concluded(tmp_path: Path) -> None:
    """The same edit, staged, is part of the merge commit, and the merge concludes."""
    subject, sibling, parent, clone = _resolving(tmp_path)
    (clone / "notes.txt").write_text("edited while resolving\n", encoding="utf-8")
    _git(clone, "add", "notes.txt")
    subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    parents = _git(clone, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
    assert len(parents) == 2, parents
    assert _git(clone, "show", "HEAD:notes.txt") == "edited while resolving", "edit left out"
