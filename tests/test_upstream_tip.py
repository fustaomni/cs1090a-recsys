"""A source's branch is resolved to its full commit by a recorded task (A.204).

upstream:checkout reads at a commit, never a branch, so the commit is resolved first, by git
ls-remote, without cloning. Only refs/heads/<branch> counts: a tag, or a longer branch ending
in the same name, is never taken for it. A missing or unreachable ref and an option-shaped
argument are refused by name. The fixture is a scratch repository whose tags, branch and
longer branches share names at three different commits.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import upstream


def _refs(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Tags develop and release on main's commit, branch develop next, feature/* on a third."""
    repo = tmp_path / "origin"
    repo.mkdir()

    def git(*args: str) -> str:
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        return done.stdout.strip()

    git("init", "--quiet", "--initial-branch=main")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    git("config", "commit.gpgsign", "false")
    git("config", "tag.gpgsign", "false")
    commits: dict[str, str] = {}
    for branch in ("main", "develop", "feature/develop"):
        if branch != "main":
            git("checkout", "--quiet", "-b", branch)
        (repo / "a.txt").write_text(f"{branch}\n", encoding="utf-8")
        git("add", "a.txt")
        git("commit", "--quiet", "-m", branch)
        commits[branch] = git("rev-parse", "HEAD")
    git("tag", "develop", commits["main"])
    git("tag", "release", commits["main"])
    git("branch", "feature/release", commits["feature/develop"])
    return repo, commits


def test_a_branch_resolves_to_its_full_commit(tmp_path: Path) -> None:
    """The branch's own commit, in full, read from a source that is never cloned."""
    assert hasattr(upstream, "tip"), "upstream:tip does not resolve a branch yet"
    repo, commits = _refs(tmp_path)
    found = upstream.tip(str(repo), "develop")
    assert found == commits["develop"], (found, commits)
    assert len(found) == 40, found


def test_a_missing_branch_is_refused_by_name(tmp_path: Path) -> None:
    """A branch the source does not have is refused, naming the branch and the source."""
    assert hasattr(upstream, "tip"), "upstream:tip does not resolve a branch yet"
    repo, _ = _refs(tmp_path)
    with pytest.raises(SystemExit) as refused:
        upstream.tip(str(repo), "nowhere")
    message = str(refused.value)
    assert "nowhere" in message, message
    assert str(repo) in message, message


def test_a_tag_or_longer_branch_is_not_taken_for_the_branch(tmp_path: Path) -> None:
    """release is only a tag and the end of feature/release, so no branch release exists."""
    assert hasattr(upstream, "tip"), "upstream:tip does not resolve a branch yet"
    repo, _ = _refs(tmp_path)
    with pytest.raises(SystemExit) as refused:
        upstream.tip(str(repo), "release")
    assert "release" in str(refused.value), refused.value


def test_an_option_shaped_argument_is_refused(tmp_path: Path) -> None:
    """Neither argument reaches git as an option: --upload-pack would run a command."""
    assert hasattr(upstream, "tip"), "upstream:tip does not resolve a branch yet"
    repo, _ = _refs(tmp_path)
    marker = tmp_path / "ran"
    for source, branch in ((f"--upload-pack=touch {marker}", "develop"), (str(repo), "--all")):
        with pytest.raises(SystemExit) as refused:
            upstream.tip(source, branch)
        assert "option" in str(refused.value), refused.value
    assert not marker.exists(), "an option-shaped source reached git"


def test_an_unreachable_source_is_refused_without_a_prompt(tmp_path: Path) -> None:
    """A source git cannot read is refused by name, and git has no terminal to prompt on."""
    assert hasattr(upstream, "tip"), "upstream:tip does not resolve a branch yet"
    absent = tmp_path / "absent"
    with pytest.raises(SystemExit) as refused:
        upstream.tip(str(absent), "develop")
    assert str(absent) in str(refused.value), refused.value
