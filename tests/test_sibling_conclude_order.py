"""A plan file resolved by hand never reaches the clone's plan-file resolver (A.216).

The resolver reads the index stages, so it cannot see a resolution already written in the
working tree, and it refuses what the stages still hold. sibling:conclude therefore stages every
conflicted path left without a marker first; only plan files still marked reach the resolver.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
PLAN = "context/plan.toml"


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _commit(repo: Path, name: str, text: str, message: str) -> None:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "--quiet", "-m", message)


def _stopped(tmp_path: Path) -> tuple[ModuleType, object, Path, Path]:
    """A sibling on feature/wip whose merge of develop stopped on a conflict in the plan."""
    subject = importlib.import_module("sibling_checkout")
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    _commit(source, "mise.toml", "[tools]\n", "config")
    _commit(source, PLAN, "base\n", "plan")
    sibling = subject.Sibling(name="demo", source=str(source), tools={"uv": "0.12.22"})
    parent = tmp_path / "siblings"
    clone = subject.checkout(sibling, parent)
    _git(clone, "config", "user.name", "t")
    _git(clone, "config", "user.email", "t@example.invalid")
    _git(clone, "switch", "--quiet", "-c", "feature/wip")
    _commit(clone, PLAN, "ours\n", "ours")
    _commit(source, PLAN, "theirs\n", "theirs")
    with pytest.raises(SystemExit):
        subject.refresh(sibling, parent, "D.1", trust=lambda _: 0)
    assert (clone / ".git" / "MERGE_HEAD").exists(), "the merge did not stop"
    return subject, sibling, parent, clone


def test_a_hand_resolved_plan_file_never_reaches_the_resolver(tmp_path: Path) -> None:
    """The plan file, rewritten without markers, is staged; the resolver is never called."""
    subject, sibling, parent, clone = _stopped(tmp_path)
    (clone / PLAN).write_text("ours\ntheirs\n", encoding="utf-8")
    called: list[Path] = []

    def resolve(path: Path) -> int:
        called.append(path)
        return 1

    try:
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=resolve)
    except SystemExit as refused:
        pytest.fail(f"a hand-resolved plan file was handed to the resolver: {refused}")
    assert called == [], called
    parents = _git(clone, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
    assert len(parents) == 2, parents
