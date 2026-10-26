"""sibling:override trusts a clone's tracked environment configs as it trusts mise.toml (A.215).

mise loads mise.<env>.toml when MISE_ENV names it, and under paranoid trust each file is trusted
by its content. A sibling's tracked FAS mode, mise.ood.toml, was never trusted, so selecting it
was refused. Each tracked mise.<env>.toml is measured as mise.toml is: unmodified at the commit
the clone is at is trusted; modified is refused by name; an untracked one is never trusted.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

ENV_CONFIG = '[task_config]\nshell = "bash -c"\n'


def _git(cwd: Path, *args: str) -> str:
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    done = subprocess.run(
        ["git", *identity, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _clone(tmp_path: Path, *, tracked: bool) -> tuple[ModuleType, object, Path, Path]:
    """A sibling whose develop commits mise.toml, and mise.ood.toml when tracked."""
    subject = importlib.import_module("sibling_checkout")
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    (source / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    _git(source, "add", "mise.toml")
    if tracked:
        (source / "mise.ood.toml").write_text(ENV_CONFIG, encoding="utf-8")
        _git(source, "add", "mise.ood.toml")
    _git(source, "commit", "--quiet", "-m", "config")
    sibling = subject.Sibling(name="demo", source=str(source), tools={"uv": "0.12.22"})
    parent = tmp_path / "siblings"
    clone = subject.checkout(sibling, parent)
    return subject, sibling, parent, clone


def test_a_tracked_env_config_unmodified_at_head_is_trusted(tmp_path: Path) -> None:
    """mise.ood.toml, as its commit holds it, is trusted with the override and mise.toml."""
    subject, sibling, parent, clone = _clone(tmp_path, tracked=True)
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    subject.refresh_override(sibling, parent, trust=trust)
    assert clone / "mise.ood.toml" in trusted, trusted


def test_a_modified_env_config_is_refused_by_name(tmp_path: Path) -> None:
    """A mise.ood.toml that differs from its commit is named in a refusal and never trusted."""
    subject, sibling, parent, clone = _clone(tmp_path, tracked=True)
    (clone / "mise.ood.toml").write_text(ENV_CONFIG + "[env]\nX = '1'\n", encoding="utf-8")
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    with pytest.raises(SystemExit) as refused:
        subject.refresh_override(sibling, parent, trust=trust)
    assert "mise.ood.toml" in str(refused.value), refused.value
    assert clone / "mise.ood.toml" not in trusted, trusted


def test_an_untracked_env_config_is_never_trusted(tmp_path: Path) -> None:
    """A mise.ood.toml no commit holds is never trusted: no review vouches for it."""
    subject, sibling, parent, clone = _clone(tmp_path, tracked=False)
    (clone / "mise.ood.toml").write_text(ENV_CONFIG, encoding="utf-8")
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    subject.refresh_override(sibling, parent, trust=trust)
    assert clone / "mise.ood.toml" not in trusted, trusted
