"""A worktree is cut from a named base, its branch untracked; with none, from fresh develop (A.93).

A stale or hardcoded base silently cuts new work from the wrong commit, so the base is explicit
first and the default is origin/develop only after a fetch. A named base is local, so it needs
no fetch: a stacked branch's unmerged parent is already here. --no-track keeps a new branch from
inheriting its base as upstream, which made it look pushed at birth (this project, 2026-09-26).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import worktree

FETCH = ("fetch", "origin", "--prune", "--quiet")


def _cut(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, argv: list[str]) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    def git(*args: str, **_: object) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(worktree, "_git", git)
    monkeypatch.setattr(worktree, "sibling_path", lambda slug: tmp_path / slug)
    monkeypatch.setattr(worktree, "_ready", lambda path, slug: 0)
    monkeypatch.setattr(sys, "argv", ["worktree.py", *argv])
    assert worktree.main() == 0
    return calls


def test_a_worktree_is_cut_from_the_named_base_untracked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _cut(monkeypatch, tmp_path, ["add", "probe", "feature/parent"])
    cut = ("worktree", "add", "--no-track", "-b", "feature/probe", str(tmp_path / "probe"))
    assert (*cut, "feature/parent") in calls, calls
    assert FETCH not in calls, calls


def test_without_a_base_it_is_cut_from_a_refreshed_origin_develop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _cut(monkeypatch, tmp_path, ["add", "probe"])
    path = str(tmp_path / "probe")
    cut = ("worktree", "add", "--no-track", "-b", "feature/probe", path, "origin/develop")
    assert FETCH in calls and cut in calls, calls
    assert calls.index(FETCH) < calls.index(cut), calls
