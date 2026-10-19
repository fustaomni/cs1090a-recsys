"""A refresh that changes mise.toml re-trusts it, through the founding gate (A.122).

mise binds trust to a config file's content, so a rebase that rewrites mise.toml leaves the
checkout untrusted, and every task in it is refused. worktree:add trusts a new checkout through
machine_trust (A.93); a finished refresh now does the same, and only when mise.toml changed.
Every boundary is faked as test_worktree_refresh.py fakes it, so nothing is rebased or trusted.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import env_sync
import machine_trust
import worktree
from env_sync import EnvironmentSync

BEFORE, AFTER, TARGET = "a" * 40, "b" * 40, "c" * 40
UNCHANGED = EnvironmentSync(lock_changed=False, installed=False, install_exit_code=None)


def _done(code: int, out: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, out, "")


def _setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, changed: bool, trusted: bool
) -> list[Path]:
    """Fake every boundary refresh crosses; return the checkouts it re-trusts."""
    heads = iter([BEFORE, AFTER])
    trusts: list[Path] = []

    def git_run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        if args == ("rev-parse", "HEAD"):
            return _done(0, next(heads))
        if args == ("rev-parse", "origin/develop"):
            return _done(0, TARGET)
        if args[0] == "diff":
            return _done(1 if changed else 0)
        return _done(0)

    def retrust(path: Path) -> machine_trust.TrustDecision:
        trusts.append(path)
        config = str(path / "mise.toml")
        return machine_trust.TrustDecision(
            config=config, sha256="0", allowed=trusted, trusted=trusted
        )

    def clean(*_: object, **__: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, b"", b"")

    monkeypatch.setattr(worktree, "sibling_path", lambda slug: tmp_path)
    monkeypatch.setattr(worktree, "git_run", git_run)
    monkeypatch.setattr(worktree, "_git", lambda *args, **kwargs: "")
    # RAISING=FALSE ONLY UNTIL GREEN: a renamed helper still fails these, since nothing calls it.
    monkeypatch.setattr(worktree, "_trust", retrust, raising=False)
    monkeypatch.setattr(subprocess, "run", clean)
    monkeypatch.setattr(env_sync, "follow_lock", lambda path, before: UNCHANGED)
    return trusts


def test_a_refresh_that_changes_mise_toml_retrusts_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trusts = _setup(monkeypatch, tmp_path, changed=True, trusted=True)
    assert worktree.cmd_refresh("probe") == 0
    assert trusts == [tmp_path], trusts


def test_a_refresh_that_leaves_mise_toml_alone_trusts_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trusts = _setup(monkeypatch, tmp_path, changed=False, trusted=True)
    assert worktree.cmd_refresh("probe") == 0
    assert trusts == [], trusts


def test_a_refused_retrust_fails_the_refresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A checkout left untrusted refuses every task, so the refresh says so instead of passing."""
    trusts = _setup(monkeypatch, tmp_path, changed=True, trusted=False)
    with pytest.raises(SystemExit, match="not trusted"):
        worktree.cmd_refresh("probe")
    assert trusts == [tmp_path], trusts
