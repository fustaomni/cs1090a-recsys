"""Another repository is read at a pinned commit, never at a moving branch (A.28).

A port reads its upstream at the exact commit it names. upstream:checkout clones blobless into
evidence, checks the commit out detached and verifies HEAD; an abbreviated SHA and a commit the
repository does not hold are refused. The fixture is a scratch repository with two commits.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

import upstream


def _repository(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "origin"
    repo.mkdir()

    def git(*args: str) -> str:
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        return done.stdout.strip()

    git("init", "--quiet", "--initial-branch=main")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    git("config", "commit.gpgsign", "false")
    (repo / "a.txt").write_text("first\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "--quiet", "-m", "first")
    first = git("rev-parse", "HEAD")
    (repo / "a.txt").write_text("second\n", encoding="utf-8")
    git("commit", "--quiet", "-am", "second")
    return repo, first, git("rev-parse", "HEAD")


def test_another_repository_is_checked_out_at_a_pinned_commit(tmp_path: Path) -> None:
    repo, first, _ = _repository(tmp_path)
    target = upstream.checkout(str(repo), first, tmp_path / "upstream")
    assert (target / "a.txt").read_text(encoding="utf-8") == "first\n"


def test_an_abbreviated_commit_is_refused(tmp_path: Path) -> None:
    repo, first, _ = _repository(tmp_path)
    with pytest.raises(SystemExit, match=re.escape("a full 40-character SHA")):
        upstream.checkout(str(repo), first[:12], tmp_path / "upstream")


def test_a_commit_not_in_the_repository_is_refused(tmp_path: Path) -> None:
    repo, _, _ = _repository(tmp_path)
    with pytest.raises(SystemExit, match=re.escape("is not in")):
        upstream.checkout(str(repo), "0" * 40, tmp_path / "upstream")


def _tree_repository(tmp_path: Path) -> tuple[Path, str]:
    """A.113: two policies and a script at the pinned commit, a third policy added after it."""
    repo = tmp_path / "tree-origin"
    repo.mkdir()

    def git(*args: str) -> str:
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        return done.stdout.strip()

    git("init", "--quiet", "--initial-branch=main")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    git("config", "commit.gpgsign", "false")
    for name in ("policies/plan/plan.rego", "policies/plan/plan_test.rego", "scripts/x.py"):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text("x\n", encoding="utf-8")
    git("add", ".")
    git("commit", "--quiet", "-m", "pinned")
    pinned = git("rev-parse", "HEAD")
    (repo / "policies" / "late").mkdir()
    (repo / "policies" / "late" / "late.rego").write_text("x\n", encoding="utf-8")
    git("add", ".")
    git("commit", "--quiet", "-m", "after the pin")
    return repo, pinned


def test_the_tree_at_a_pinned_commit_is_listed_from_its_trees(tmp_path: Path) -> None:
    """A.113: every path under a pathspec at the pin, and nothing the repository added after it."""
    assert hasattr(upstream, "tree"), "upstream:checkout cannot list a tree yet"
    repo, pinned = _tree_repository(tmp_path)
    listed = upstream.tree(str(repo), pinned, ("policies",), tmp_path / "upstream")
    assert listed == ("policies/plan/plan.rego", "policies/plan/plan_test.rego"), listed


def test_a_pathspec_matching_nothing_is_refused_by_name(tmp_path: Path) -> None:
    """A.182: git ls-tree takes literal paths, so a wildcard matches nothing; that is refused."""
    repo, pinned = _tree_repository(tmp_path)
    specs = ("policies", "policies/plan/*.rego", "docs")
    with pytest.raises(SystemExit) as refused:
        upstream.tree(str(repo), pinned, specs, tmp_path / "upstream")
    message = str(refused.value)
    assert "policies/plan/*.rego" in message, message
    assert "docs" in message, message
    assert "literal" in message, message


def test_a_literal_file_and_a_literal_directory_are_listed_together(tmp_path: Path) -> None:
    """A.182: every pathspec that names a path at the pin still lists it."""
    repo, pinned = _tree_repository(tmp_path)
    specs = ("scripts/x.py", "policies/plan")
    listed = upstream.tree(str(repo), pinned, specs, tmp_path / "upstream")
    expected = ("policies/plan/plan.rego", "policies/plan/plan_test.rego", "scripts/x.py")
    assert listed == expected, listed


def _twin_repositories(tmp_path: Path) -> tuple[Path, Path, str]:
    """A.184: two sources named origin, the second cloned from the first: one name, one commit."""
    (tmp_path / "one").mkdir()
    first, commit, _ = _repository(tmp_path / "one")
    second = tmp_path / "two" / "origin"
    second.parent.mkdir()
    clone = ["git", "clone", "--quiet", str(first), str(second)]
    subprocess.run(clone, capture_output=True, text=True, check=True)
    return first, second, commit


def test_two_sources_sharing_a_name_and_commit_get_their_own_checkouts(tmp_path: Path) -> None:
    """A.184: a clone is named by its source, so a second source is never served the first's."""
    first, second, commit = _twin_repositories(tmp_path)
    root = tmp_path / "upstream"
    one = upstream.checkout(str(first), commit, root)
    two = upstream.checkout(str(second), commit, root)
    assert one != two, (one, two)
    origin = ["git", "remote", "get-url", "origin"]
    read = subprocess.run(origin, cwd=two, capture_output=True, text=True, check=True)
    assert read.stdout.strip() == str(second), read.stdout


def test_a_checkout_whose_origin_is_another_source_is_refused(tmp_path: Path) -> None:
    """A.184: an existing clone is reused only after its origin is read back as the source."""
    assert hasattr(upstream, "location"), "upstream:checkout does not name a clone by its source"
    first, second, commit = _twin_repositories(tmp_path)
    root = tmp_path / "upstream"
    made = upstream.checkout(str(first), commit, root)
    made.rename(upstream.location(str(second), commit, root))
    with pytest.raises(SystemExit) as refused:
        upstream.checkout(str(second), commit, root)
    assert str(first) in str(refused.value), refused.value
