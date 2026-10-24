"""sibling:refresh merges a named ref of a sibling's origin into its feature branch (A.209).

A sibling clone on a feature branch takes in its declared branch, or any ref its origin has, by
a merge commit and never a rebase. The merge is staged without committing, a merged mise.toml is
trusted only when byte-identical to a reviewed commit, and only then is the merge committed, so
the clone's own hooks run against a trusted config. A conflict stops with its files named and
nothing committed; a ref the origin lacks is refused by name.
"""

from __future__ import annotations

import importlib
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


def _subject() -> ModuleType:
    subject = importlib.import_module("sibling_checkout")
    assert hasattr(subject, "refresh"), "no task merges a ref into a sibling's feature branch"
    return subject


def _clone(tmp_path: Path) -> tuple[ModuleType, object, Path, Path, Path]:
    """An origin on develop, cloned as sibling:checkout clones, then put on feature/wip."""
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
    _commit(clone, "g.txt", "work\n", "work")
    return subject, sibling, parent, clone, source


def _parents(clone: Path) -> list[str]:
    return _git(clone, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]


def test_the_declared_branch_is_merged_with_a_merge_commit(tmp_path: Path) -> None:
    """develop's new commit arrives by a merge commit that names the plan step."""
    _, sibling, parent, clone, source = _clone(tmp_path)
    _commit(source, "h.txt", "new\n", "upstream")
    subject = _subject()
    subject.refresh(sibling, parent, "D.1", trust=lambda _: 0)
    assert _parents(clone)[1:] == [_git(source, "rev-parse", "develop")], _parents(clone)
    assert "Plan-Step: D.1" in _git(clone, "log", "-1", "--format=%B"), "no step named"


def test_a_merged_config_from_a_reviewed_commit_is_trusted_before_the_commit(
    tmp_path: Path,
) -> None:
    """develop's mise.toml is trusted while the merge is still staged, then committed."""
    _, sibling, parent, clone, source = _clone(tmp_path)
    _commit(source, "mise.toml", "[tools]\nuv = '1'\n", "config moved")
    subject = _subject()
    staged: list[tuple[Path, bool]] = []

    def trust(path: Path) -> int:
        staged.append((path, (clone / ".git" / "MERGE_HEAD").exists()))
        return 0

    subject.refresh(sibling, parent, "D.1", trust=trust)
    assert (clone / "mise.toml", True) in staged, staged
    assert len(_parents(clone)) == 2, "the merge was not committed"


def test_a_conflict_stops_naming_its_files_and_commits_nothing(tmp_path: Path) -> None:
    """Both sides changed f.txt: the refusal names it, and HEAD does not move."""
    _, sibling, parent, clone, source = _clone(tmp_path)
    _commit(source, "f.txt", "theirs\n", "upstream edit")
    _commit(clone, "f.txt", "ours\n", "local edit")
    before = _git(clone, "rev-parse", "HEAD")
    subject = _subject()
    with pytest.raises(SystemExit) as refused:
        subject.refresh(sibling, parent, "D.1", trust=lambda _: 0)
    assert "f.txt" in str(refused.value), refused.value
    assert _git(clone, "rev-parse", "HEAD") == before, "a conflicted merge was committed"


def test_a_named_ref_is_merged_and_one_origin_lacks_is_refused(tmp_path: Path) -> None:
    """origin/feature/fix is merged when named; a ref the origin lacks is refused by name."""
    _, sibling, parent, clone, source = _clone(tmp_path)
    _git(source, "switch", "--quiet", "-c", "feature/fix")
    _commit(source, "fix.txt", "fixed\n", "the fix")
    _git(source, "switch", "--quiet", "develop")
    subject = _subject()
    subject.refresh(sibling, parent, "D.1", "feature/fix", trust=lambda _: 0)
    assert _parents(clone)[1:] == [_git(source, "rev-parse", "feature/fix")], _parents(clone)
    with pytest.raises(SystemExit) as refused:
        subject.refresh(sibling, parent, "D.1", "no-such-branch", trust=lambda _: 0)
    assert "no-such-branch" in str(refused.value), refused.value
