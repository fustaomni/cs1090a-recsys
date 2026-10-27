"""A merged mise.toml its reviewer named against this HEAD concludes the merge (A.218).

When both sides change a sibling's mise.toml, the merged file matches neither parent, so
parent equality alone refuses every such merge. sibling:trust shows that merged content and
records the digest its reviewer named against HEAD; sibling:conclude accepts exactly that
content, and still refuses any other, and a review made against another HEAD.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
BASE = "[tools]\nuv = '0'\n\n# one\n# two\n# three\n# four\n# five\n\n[env]\nX = '0'\n"


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _commit(repo: Path, name: str, text: str, message: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "--quiet", "-m", message)


def _stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[ModuleType, object, Path, Path]:
    """Both sides change mise.toml apart, f.txt conflicts, and f.txt is resolved by hand."""
    subject = importlib.import_module("sibling_checkout")
    monkeypatch.setattr(subject, "TRUST_RECORDS", tmp_path / "trust", raising=False)
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    _commit(source, "mise.toml", BASE, "config")
    _commit(source, "f.txt", "base\n", "base")
    sibling = subject.Sibling(name="demo", source=str(source), tools={"uv": "0.12.22"})
    parent = tmp_path / "siblings"
    clone = subject.checkout(sibling, parent)
    _git(clone, "config", "user.name", "t")
    _git(clone, "config", "user.email", "t@example.invalid")
    _git(clone, "switch", "--quiet", "-c", "feature/wip")
    _commit(clone, "mise.toml", BASE.replace("X = '0'", "X = '1'"), "ours: config")
    _commit(clone, "f.txt", "ours\n", "ours")
    _commit(source, "mise.toml", BASE.replace("uv = '0'", "uv = '1'"), "theirs: config")
    _commit(source, "f.txt", "theirs\n", "theirs")
    with pytest.raises(SystemExit) as refused:
        subject.refresh(sibling, parent, "D.1", trust=lambda _: 0)
    assert "f.txt" in str(refused.value), refused.value
    (clone / "f.txt").write_text("resolved\n", encoding="utf-8")
    return subject, sibling, parent, clone


def _digest(clone: Path) -> str:
    return hashlib.sha256((clone / "mise.toml").read_bytes()).hexdigest()


def test_a_merged_config_reviewed_against_head_is_concluded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reviewed merged config is trusted, and the merge commits with both changes."""
    subject, sibling, parent, clone = _stopped(tmp_path, monkeypatch)
    subject.review(sibling, parent, _digest(clone), trust=lambda _: 0)
    try:
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    except SystemExit as refused:
        pytest.fail(f"a merged config reviewed against HEAD was refused: {refused}")
    parents = _git(clone, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
    assert len(parents) == 2, parents
    committed = _git(clone, "show", "HEAD:mise.toml")
    assert "X = '1'" in committed and "uv = '1'" in committed, committed


def test_an_unreviewed_merged_config_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no review, a config matching neither parent is refused and the merge kept."""
    subject, sibling, parent, clone = _stopped(tmp_path, monkeypatch)
    with pytest.raises(SystemExit, match="matches neither"):
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    assert (clone / ".git" / "MERGE_HEAD").exists(), "the refused merge was not kept"


def test_a_review_against_another_head_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record at the right digest but made against another HEAD is stale, and refused."""
    subject, sibling, parent, clone = _stopped(tmp_path, monkeypatch)
    record = tmp_path / "trust" / "demo.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    stale = {"sibling": "demo", "config": "mise.toml", "commit": "0" * 40, "sha256": _digest(clone)}
    record.write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(SystemExit, match="matches neither"):
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    assert (clone / ".git" / "MERGE_HEAD").exists(), "the refused merge was not kept"
