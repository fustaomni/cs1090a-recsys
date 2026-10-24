"""sibling:conclude finishes a sibling merge that stopped on conflicts (A.210).

sibling:refresh stops a merge on its first conflict and leaves it in progress. The clone's own
plan-file resolver settles the plan files; anything else is resolved and staged by hand. Only
then is the merge concluded: refused while a path stays unmerged or a conflict marker remains
in a staged file, its mise.toml trusted as A.209 trusts it, and the commit names the plan step.
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


def _subject() -> ModuleType:
    subject = importlib.import_module("sibling_checkout")
    assert hasattr(subject, "conclude"), "no task concludes a sibling merge"
    return subject


def _stopped(tmp_path: Path, name: str) -> tuple[ModuleType, object, Path, Path]:
    """A sibling on feature/wip whose merge of develop stopped on a conflict in name."""
    subject = importlib.import_module("sibling_checkout")
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    _commit(source, "mise.toml", "[tools]\n", "config")
    _commit(source, "f.txt", "base\n", "base")
    _commit(source, PLAN, "base\n", "plan")
    sibling = subject.Sibling(name="demo", source=str(source), tools={"uv": "0.12.22"})
    parent = tmp_path / "siblings"
    clone = subject.checkout(sibling, parent)
    _git(clone, "config", "user.name", "t")
    _git(clone, "config", "user.email", "t@example.invalid")
    _git(clone, "switch", "--quiet", "-c", "feature/wip")
    _commit(clone, name, "ours\n", "ours")
    _commit(source, name, "theirs\n", "theirs")
    with pytest.raises(SystemExit):
        subject.refresh(sibling, parent, "D.1", trust=lambda _: 0)
    assert (clone / ".git" / "MERGE_HEAD").exists(), "the merge did not stop"
    return subject, sibling, parent, clone


def test_plan_files_are_resolved_by_the_clones_resolver_then_committed(tmp_path: Path) -> None:
    """The clone's resolver settles the plan file, then the merge commit names the step."""
    _, sibling, parent, clone = _stopped(tmp_path, PLAN)
    subject = _subject()
    called: list[Path] = []

    def resolve(path: Path) -> int:
        called.append(path)
        (path / PLAN).write_text("ours\ntheirs\n", encoding="utf-8")
        _git(path, "add", PLAN)
        return 0

    subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=resolve)
    assert called == [clone], called
    parents = _git(clone, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
    assert len(parents) == 2, parents
    assert "Plan-Step: D.1" in _git(clone, "log", "-1", "--format=%B"), "no step named"


def test_an_unmerged_path_left_is_refused_and_nothing_committed(tmp_path: Path) -> None:
    """f.txt is still unmerged: the refusal names it, and HEAD does not move."""
    _, sibling, parent, clone = _stopped(tmp_path, "f.txt")
    before = _git(clone, "rev-parse", "HEAD")
    subject = _subject()
    with pytest.raises(SystemExit) as refused:
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    assert "f.txt" in str(refused.value), refused.value
    assert _git(clone, "rev-parse", "HEAD") == before, "a merge with an unmerged path was committed"


def test_a_conflict_marker_left_is_refused_and_nothing_committed(tmp_path: Path) -> None:
    """f.txt was staged with its markers still in it: refused by name, nothing committed."""
    _, sibling, parent, clone = _stopped(tmp_path, "f.txt")
    _git(clone, "add", "f.txt")
    before = _git(clone, "rev-parse", "HEAD")
    subject = _subject()
    with pytest.raises(SystemExit) as refused:
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    assert "f.txt" in str(refused.value), refused.value
    assert _git(clone, "rev-parse", "HEAD") == before, "a merge holding markers was committed"


def test_no_merge_in_progress_is_refused(tmp_path: Path) -> None:
    """With nothing stopped, there is nothing to conclude, and it says so."""
    subject = importlib.import_module("sibling_checkout")
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    _commit(source, "mise.toml", "[tools]\n", "config")
    sibling = subject.Sibling(name="demo", source=str(source), tools={"uv": "0.12.22"})
    parent = tmp_path / "siblings"
    clone = subject.checkout(sibling, parent)
    _git(clone, "switch", "--quiet", "-c", "feature/wip")
    subject = _subject()
    with pytest.raises(SystemExit) as refused:
        subject.conclude(sibling, parent, "D.1", trust=lambda _: 0, resolve=lambda _: 0)
    assert "no merge" in str(refused.value), refused.value
