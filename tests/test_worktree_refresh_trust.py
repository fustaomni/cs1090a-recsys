"""A refresh trusts a merged mise.toml before it commits the merge (A.207).

Under paranoid trust a merge that changes mise.toml leaves it untrusted, and the merge commit runs
commit-msg, whose plan steps job calls mise. A.191's refresh committed the merge first and trusted
afterwards, so the hook refused and git left the merge uncommitted. Refresh now merges without
committing, gates and trusts a changed mise.toml, and only then commits; a refused one is never
committed. git, the trust, the fetch and follow_lock are all faked, so nothing is merged.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import env_sync
import worktree
from env_sync import EnvironmentSync

BEFORE, AFTER, TARGET = "a" * 40, "b" * 40, "c" * 40
UNCHANGED = EnvironmentSync(lock_changed=False, installed=False, install_exit_code=None)


def _done(code: int, out: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, out, "")


def _setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, changed: bool, trusted: bool
) -> list[tuple[str, ...]]:
    """Fake every boundary refresh crosses; return each git call and each trust, in order."""
    events: list[tuple[str, ...]] = []
    heads = iter([BEFORE, AFTER])

    def git_run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        events.append(args)
        if args == ("rev-parse", "HEAD"):
            return _done(0, next(heads))
        if args == ("rev-parse", "origin/develop"):
            return _done(0, TARGET)
        if args[0] == "diff":
            return _done(1 if changed else 0)
        return _done(0)

    def trust(path: Path) -> SimpleNamespace:
        events.append(("trust",))
        return SimpleNamespace(trusted=trusted)

    def clean(*_: object, **__: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, b"", b"")

    monkeypatch.setattr(worktree, "sibling_path", lambda slug: tmp_path)
    monkeypatch.setattr(worktree, "git_run", git_run)
    monkeypatch.setattr(worktree, "_git", lambda *args, **kwargs: "")
    monkeypatch.setattr(worktree, "_trust", trust)
    # THE STDLIB MODULE ITSELF: worktree only imports it, and imports are not re-exported.
    monkeypatch.setattr(subprocess, "run", clean)
    monkeypatch.setattr(env_sync, "follow_lock", lambda path, before: UNCHANGED)
    return events


def _merge(events: list[tuple[str, ...]]) -> tuple[str, ...]:
    return next(event for event in events if event[0] == "merge")


def test_a_merge_that_changes_mise_toml_is_trusted_before_it_is_committed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The merge is staged, the changed mise.toml trusted, and only then is the merge committed."""
    events = _setup(monkeypatch, tmp_path, changed=True, trusted=True)
    assert worktree.cmd_refresh("probe", "A.1") == 0
    assert "--no-commit" in _merge(events), _merge(events)
    names = [event[0] for event in events]
    assert "commit" in names, names
    assert names.index("trust") < names.index("commit"), names


def test_a_merged_mise_toml_the_founding_policy_refuses_is_not_committed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A changed mise.toml that is not trusted stops the refresh before any commit is made."""
    events = _setup(monkeypatch, tmp_path, changed=True, trusted=False)
    with pytest.raises(SystemExit) as refused:
        worktree.cmd_refresh("probe", "A.1")
    assert "--no-commit" in _merge(events), _merge(events)
    names = [event[0] for event in events]
    assert "commit" not in names, names
    assert "mise.toml" in str(refused.value.code), refused.value.code


def test_a_merge_that_leaves_mise_toml_alone_commits_without_a_trust(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unchanged mise.toml is not trusted again, and the merge is still committed."""
    events = _setup(monkeypatch, tmp_path, changed=False, trusted=True)
    assert worktree.cmd_refresh("probe", "A.1") == 0
    names = [event[0] for event in events]
    assert "trust" not in names, names
    assert "commit" in names, names
