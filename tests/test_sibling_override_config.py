"""sibling:override trusts the clone's own mise.toml once judged unmodified (A.208).

Under paranoid trust each config file is trusted by its content. A sibling switched to a feature
branch carries that branch's mise.toml, and an override that trusted only the mise.local.toml it
writes left every task in the clone refused. The clone's mise.toml is measured as sibling:checkout
measures it: unmodified at the commit the clone is at is trusted by path; modified is refused and
never trusted; a trust mise refuses is refused by name.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def _git(cwd: Path, *args: str) -> str:
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    done = subprocess.run(
        ["git", *identity, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _clone(tmp_path: Path) -> tuple[ModuleType, object, Path, Path]:
    """A sibling whose develop commits a mise.toml, cloned the way sibling:checkout clones."""
    subject = importlib.import_module("sibling_checkout")
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    (source / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    _git(source, "add", "mise.toml")
    _git(source, "commit", "--quiet", "-m", "config")
    sibling = subject.Sibling(name="demo", source=str(source), tools={"uv": "0.12.22"})
    parent = tmp_path / "siblings"
    clone = subject.checkout(sibling, parent)
    return subject, sibling, parent, clone


def test_an_unmodified_config_is_trusted_with_the_override(tmp_path: Path) -> None:
    """The override and the clone's own mise.toml are both trusted, each by its path."""
    subject, sibling, parent, clone = _clone(tmp_path)
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    subject.refresh_override(sibling, parent, trust=trust)
    assert clone / "mise.toml" in trusted, trusted
    assert clone / "mise.local.toml" in trusted, trusted


def test_a_modified_config_is_refused_and_not_trusted(tmp_path: Path) -> None:
    """A mise.toml that differs from its commit is named in a refusal and never trusted."""
    subject, sibling, parent, clone = _clone(tmp_path)
    (clone / "mise.toml").write_text("[tools]\nuntrusted = '1'\n", encoding="utf-8")
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    with pytest.raises(SystemExit) as refused:
        subject.refresh_override(sibling, parent, trust=trust)
    assert "mise.toml" in str(refused.value), refused.value
    assert clone / "mise.toml" not in trusted, trusted


def test_a_config_mise_will_not_trust_is_refused(tmp_path: Path) -> None:
    """When mise refuses to trust the clone's mise.toml, the override says so by name."""
    subject, sibling, parent, clone = _clone(tmp_path)

    def trust(path: Path) -> int:
        return 1 if path.name == "mise.toml" else 0

    with pytest.raises(SystemExit) as refused:
        subject.refresh_override(sibling, parent, trust=trust)
    assert str(clone / "mise.toml") in str(refused.value), refused.value
