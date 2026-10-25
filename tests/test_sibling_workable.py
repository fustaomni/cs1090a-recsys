"""A stopped sibling merge stays workable (A.212).

When sibling:refresh stops on a conflict, the merge has already rewritten the clone's files,
mise.toml among them. If a reviewed commit holds that config, it is trusted before the
conflict is reported, so the clone's own tasks still run. The conflict blocks are read as
data from the clone, and a path resolved by hand, with no marker left, is staged by
sibling:conclude rather than refused.
"""

from __future__ import annotations

import importlib
import json
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


def _stop(tmp_path: Path, trust: object) -> tuple[ModuleType, object, Path, Path]:
    """develop moves mise.toml and f.txt, the clone moves f.txt, and the merge stops on f.txt."""
    subject = importlib.import_module("sibling_checkout")
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    _commit(source, "mise.toml", "[tools]\n", "config")
    _commit(source, "f.txt", "base\n", "base")
    sibling = subject.Sibling(name="demo", source=str(source), tools={"uv": "0.12.22"})
    parent = tmp_path / "siblings"
    clone = subject.checkout(sibling, parent)
    _git(clone, "config", "user.name", "t")
    _git(clone, "config", "user.email", "t@example.invalid")
    _git(clone, "switch", "--quiet", "-c", "feature/wip")
    _commit(clone, "f.txt", "ours\n", "ours")
    _commit(source, "mise.toml", "[tools]\nuv = '1'\n", "config moved")
    _commit(source, "f.txt", "theirs\n", "theirs")
    with pytest.raises(SystemExit) as refused:
        subject.refresh(sibling, parent, "D.1", trust=trust)
    assert "f.txt" in str(refused.value), refused.value
    return subject, sibling, parent, clone


def test_a_stopped_merge_leaves_its_reviewed_config_trusted(tmp_path: Path) -> None:
    """develop's mise.toml is trusted while the stopped merge is still in progress."""
    staged: list[tuple[Path, bool]] = []
    clone_root = tmp_path / "siblings" / "demo"

    def trust(path: Path) -> int:
        staged.append((path, (clone_root / ".git" / "MERGE_HEAD").exists()))
        return 0

    _, _, _, clone = _stop(tmp_path, trust)
    assert (clone / "mise.toml", True) in staged, staged


def test_the_conflict_blocks_are_read_as_data(tmp_path: Path) -> None:
    """The report names f.txt and carries both sides of its conflict."""
    subject, sibling, parent, _ = _stop(tmp_path, lambda _: 0)
    assert hasattr(subject, "sibling_conflicts"), "no task reads a sibling's conflicts"
    report = subject.sibling_conflicts(sibling, parent)
    dumped = json.dumps(report.model_dump(mode="json"))
    assert "f.txt" in dumped, dumped
    assert "ours" in dumped and "theirs" in dumped, dumped


def test_a_refused_conclusion_leaves_its_reviewed_config_trusted(tmp_path: Path) -> None:
    """A merge that stopped before this fix is made workable by conclude, even as it refuses."""
    subject, sibling, parent, clone = _stop(tmp_path, lambda _: 0)
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    with pytest.raises(SystemExit):
        subject.conclude(sibling, parent, "D.1", trust=trust, resolve=lambda _: 0)
    assert clone / "mise.toml" in trusted, trusted


def test_a_hand_resolved_path_is_staged_and_concluded(tmp_path: Path) -> None:
    """f.txt rewritten without markers, never staged by hand, is staged and the merge committed."""
    subject, sibling, parent, clone = _stop(tmp_path, lambda _: 0)
    (clone / "f.txt").write_text("resolved\n", encoding="utf-8")
    try:
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    except SystemExit as refused:
        pytest.fail(f"a hand-resolved path was refused instead of staged: {refused}")
    parents = _git(clone, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
    assert len(parents) == 2, parents
    assert _git(clone, "show", "HEAD:f.txt") == "resolved", "the resolution was not committed"
