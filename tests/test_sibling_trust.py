"""sibling:trust trusts an edited sibling config only at the digest its reviewer names (A.211).

Under paranoid trust an edited mise.toml is untrusted, so a sibling whose tasks are being added
on this machine could run none of them, its commit hooks included. sibling:override trusts only
what a commit reviewed. sibling:trust shows the change against the commit with its digest, and
trusts the file only when it still hashes to the digest the reviewer names.
"""

from __future__ import annotations

import hashlib
import importlib
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

EDITED = '[tools]\n\n[tasks."new:task"]\nrun = "true"\n'


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


def _review(subject: ModuleType) -> Callable[..., str]:
    review: Callable[..., str] | None = getattr(subject, "review", None)
    assert review is not None, "sibling:trust has no review"
    return review


def test_the_named_digest_is_trusted_after_the_change_is_shown(tmp_path: Path) -> None:
    """Shown first with its digest, then trusted when the reviewer names that digest."""
    subject, sibling, parent, clone = _clone(tmp_path)
    review = _review(subject)
    (clone / "mise.toml").write_text(EDITED, encoding="utf-8")
    digest = hashlib.sha256(EDITED.encode("utf-8")).hexdigest()
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    with pytest.raises(SystemExit) as shown:
        review(sibling, parent, None, trust=trust)
    assert digest in str(shown.value) and "new:task" in str(shown.value), shown.value
    assert trusted == [], trusted
    review(sibling, parent, digest, trust=trust)
    assert trusted == [clone / "mise.toml"], trusted


def test_a_different_digest_is_refused_and_nothing_trusted(tmp_path: Path) -> None:
    """A digest the content does not hash to is refused, and nothing is trusted."""
    subject, sibling, parent, clone = _clone(tmp_path)
    review = _review(subject)
    (clone / "mise.toml").write_text(EDITED, encoding="utf-8")
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    with pytest.raises(SystemExit) as refused:
        review(sibling, parent, "0" * 64, trust=trust)
    assert "digest" in str(refused.value), refused.value
    assert trusted == [], trusted


def test_an_unmodified_config_is_refused_as_needing_no_review(tmp_path: Path) -> None:
    """A config its commit holds needs no review: sibling:override already trusts it."""
    subject, sibling, parent, _ = _clone(tmp_path)
    review = _review(subject)
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    with pytest.raises(SystemExit) as refused:
        review(sibling, parent, None, trust=trust)
    assert "no review" in str(refused.value), refused.value
    assert trusted == [], trusted
