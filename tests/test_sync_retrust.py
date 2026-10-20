# tests/test_sync_retrust.py
"""A sync whose pull rewrote mise.toml re-trusts it through the founding gate, or fails (A.126).

Under paranoid mode mise binds trust to a config's content, and its 2026 cross-worktree trust
sharing excludes paranoid mode, so every pull that rewrites mise.toml leaves the checkout
untrusted until something trusts it again. worktree:refresh re-trusts since A.122; sync now
does the same, through the same _trust, and only when the pull changed mise.toml.

A REAL REPOSITORY; ONLY THE TRUST IS FAKED, as test_sync_environment.py fakes only uv.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import machine_trust
import sync


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(tmp_path: Path, second: str) -> tuple[Path, str]:
    """Two commits; the second changes `second`. Returns the repository and the first."""
    _git(tmp_path, "init", "-q", "-b", "develop")
    (tmp_path / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "first")
    before = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / second).write_text("changed\n", encoding="utf-8")
    _git(tmp_path, "commit", "-q", "-am", "second")
    return tmp_path, before


def _trusts(monkeypatch: pytest.MonkeyPatch, *, trusted: bool) -> list[Path]:
    """Replace the one trust path; return the checkouts it was asked to trust."""
    seen: list[Path] = []

    def fake(path: Path) -> machine_trust.TrustDecision:
        seen.append(path)
        config = str(path / "mise.toml")
        return machine_trust.TrustDecision(
            config=config, sha256="0", allowed=trusted, trusted=trusted
        )

    # RAISING, PYTEST'S DEFAULT (A.133): a renamed helper fails here, at the patch, by name.
    monkeypatch.setattr(sync, "_trust", fake)
    return seen


def test_a_sync_that_changes_mise_toml_retrusts_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, before = _repo(tmp_path, "mise.toml")
    trusts = _trusts(monkeypatch, trusted=True)
    sync.retrust_if_rewritten(repo, before)
    assert trusts == [repo], trusts


def test_a_sync_that_leaves_mise_toml_alone_trusts_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, before = _repo(tmp_path, "notes.txt")
    trusts = _trusts(monkeypatch, trusted=True)
    sync.retrust_if_rewritten(repo, before)
    assert trusts == [], trusts


def test_a_refused_retrust_fails_the_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, before = _repo(tmp_path, "mise.toml")
    trusts = _trusts(monkeypatch, trusted=False)
    with pytest.raises(SystemExit, match="not trusted"):
        sync.retrust_if_rewritten(repo, before)
    assert trusts == [repo], trusts
