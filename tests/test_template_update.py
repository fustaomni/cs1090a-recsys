# tests/test_template_update.py
"""A generated project takes its template's later commit, and a conflict is reported (A.134).

A REAL TEMPLATE AND A REAL PROJECT, offline: a local template repository with two commits, and a
project Copier generated from the first, committed and on a feature branch. Only the declared
repository is replaced, so the template under test counts as this one.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from copier import run_copy

import template_update

ANSWERS = "{{ _copier_conf.answers_file }}.jinja"


@pytest.fixture(autouse=True)
def _identity(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare HOME, and an author for the commits Copier makes in its own scratch clones."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "t")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "t@example.invalid")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _template(tmp_path: Path, later: dict[str, str]) -> tuple[Path, str, str]:
    """A template holding a.txt at its first commit; its second commit writes `later`."""
    source = tmp_path / "tmpl.git"
    source.mkdir()
    _git(source, "init", "-q", "-b", "main")
    (source / "copier.yml").write_text("_answers_file: .copier-answers.yml\n", encoding="utf-8")
    (source / ANSWERS).write_text("{{ _copier_answers|to_nice_yaml -}}\n", encoding="utf-8")
    (source / "a.txt").write_text("one\nshared\nthree\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-q", "-m", "first")
    first = _git(source, "rev-parse", "HEAD")
    for name, text in later.items():
        (source / name).write_text(text, encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-q", "-m", "second")
    return source, first, _git(source, "rev-parse", "HEAD")


def _project(tmp_path: Path, source: Path, first: str) -> Path:
    """Generated at the first commit, committed, and on a feature branch."""
    project = tmp_path / "project"
    run_copy(str(source), str(project), vcs_ref=first, defaults=True, quiet=True)
    _git(project, "init", "-q", "-b", "main")
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "generated")
    _git(project, "switch", "-q", "-c", "feature/update")
    return project


def _declare(monkeypatch: pytest.MonkeyPatch, source: Path) -> None:
    """This repository's declared template is the local one under test."""
    declared = SimpleNamespace(repository=str(source).removesuffix(".git"))
    monkeypatch.setattr(template_update, "load", lambda root: declared)


def _outcome(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    envelope = json.loads(capsys.readouterr().out)
    assert isinstance(envelope, dict), envelope
    return envelope


def test_a_generated_project_takes_its_templates_later_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source, first, second = _template(tmp_path, {"b.txt": "added later\n"})
    project = _project(tmp_path, source, first)
    _declare(monkeypatch, source)
    assert template_update.main([str(project), second]) == 0
    outcome = _outcome(capsys)
    assert outcome["code"] == "project_updated", outcome
    assert (project / "b.txt").read_text(encoding="utf-8") == "added later\n"
    answers = yaml.safe_load((project / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert second.startswith(answers["_commit"]), answers


def test_a_conflicting_update_is_reported_by_its_rej_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source, first, second = _template(tmp_path, {"a.txt": "one\ntemplate\nthree\n"})
    project = _project(tmp_path, source, first)
    (project / "a.txt").write_text("one\nproject\nthree\n", encoding="utf-8")
    _git(project, "commit", "-q", "-am", "local")
    _declare(monkeypatch, source)
    assert template_update.main([str(project), second]) != 0
    outcome = _outcome(capsys)
    assert outcome["code"] == "update_conflicted", outcome
    assert "a.txt.rej" in str(outcome["message"]), outcome
