"""History is rewritten only into a separate mirror, by rules given as data (A.364).

The rules name the message lines to drop, the text to replace, and the paths whose commit
citations are remapped. history:rewrite clones the source into a fresh mirror, rewrites it there
through git-filter-repo's library, and verifies the result. It never pushes, and it refuses to
write into a repository that already exists. These run real git in scratch repositories.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from nonvacuous import nonempty

KEEP = "Plan-Step: A.1"
DROPPED = "Scratch-Drop: zqx"
REFS = "--format=%(objectname) %(refname)"


def _subject() -> ModuleType:
    return importlib.import_module("history_rewrite")


def _git(repo: Path, *argv: str) -> str:
    done = subprocess.run(["git", *argv], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _scratch(tmp_path: Path) -> Path:
    """An empty source repository on develop; no signing, no hooks."""
    repo = tmp_path / "source"
    repo.mkdir()
    for argv in (
        ["init", "-q", "-b", "develop"],
        ["config", "user.name", "zqx"],
        ["config", "user.email", "zqx"],
        ["config", "commit.gpgsign", "false"],
        ["config", "core.hooksPath", str(repo / ".no-hooks")],
    ):
        _git(repo, *argv)
    return repo


def _commit(repo: Path, name: str, text: str, message: str) -> str:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _rules(drop: list[str], replace: list[dict[str, str]], cited: list[str]) -> object:
    fields = {"drop_lines": drop, "replace_text": replace, "cited_paths": cited}
    return _subject().RewriteRules.model_validate(fields)


def test_every_message_line_the_rules_drop_is_gone_from_the_mirror(tmp_path: Path) -> None:
    source = _scratch(tmp_path)
    _commit(source, "a.txt", "zqx words\n", f"chore(scratch): one\n\n{KEEP}\n{DROPPED}")
    _commit(source, "b.txt", "plain\n", f"chore(scratch): two\n\n{DROPPED}\n{KEEP}")
    replace = [{"find": "zqx words", "replace": "kept words"}]
    rules = _rules(["^Scratch-Drop:"], replace, [])
    mirror = tmp_path / "mirror.git"
    report = _subject().rewrite(str(source), mirror, rules)
    messages = _git(mirror, "log", "--all", "--format=%B%x00").split("\x00")
    for message in nonempty(text for text in messages if text.strip()):
        assert DROPPED not in message
        assert KEEP in message
    assert "zqx words" not in _git(mirror, "log", "--all", "-p", "--format=")
    assert _git(mirror, "show", "develop:a.txt") == "kept words"
    assert report.remaining_matches == 0


def test_every_cited_commit_id_is_remapped_to_its_rewritten_commit(tmp_path: Path) -> None:
    source = _scratch(tmp_path)
    first = _commit(source, "a.txt", "one\n", f"chore(scratch): one\n\n{KEEP}\n{DROPPED}")
    cites = f"full {first}\nshort {first[:7]}\n"
    second = _commit(source, "cites.txt", cites, f"chore(scratch): two\n\n{KEEP}")
    _commit(source, "later.txt", f"cites {second}\n", f"chore(scratch): three\n\n{KEEP}")
    rules = _rules(["^Scratch-Drop:"], [], ["cites.txt", "later.txt"])
    mirror = tmp_path / "mirror.git"
    report = _subject().rewrite(str(source), mirror, rules)
    new_first = report.rewritten[first]
    new_second = report.rewritten[second]
    assert new_first != first
    assert new_second != second
    remapped = f"full {new_first}\nshort {new_first[:7]}"
    assert _git(mirror, "show", "develop:cites.txt") == remapped
    assert _git(mirror, "show", "develop:later.txt") == f"cites {new_second}"
    assert report.stale_citations == 0
    assert report.citation_passes >= 2


def test_the_rewrite_never_pushes_and_refuses_a_working_checkout(tmp_path: Path) -> None:
    subject = _subject()
    source = _scratch(tmp_path)
    _commit(source, "a.txt", "one\n", f"chore(scratch): one\n\n{KEEP}\n{DROPPED}")
    before = _git(source, "for-each-ref", REFS)
    rules = _rules(["^Scratch-Drop:"], [], [])
    with pytest.raises(subject.RewriteRefused):
        subject.rewrite(str(source), source, rules)
    mirror = tmp_path / "mirror.git"
    subject.rewrite(str(source), mirror, rules)
    assert _git(source, "for-each-ref", REFS) == before
    assert _git(source, "log", "-1", "--format=%B").count(DROPPED) == 1
    assert _git(mirror, "remote") == ""
