# tests/test_copier_template.py
"""The platform generates a new project as a Copier template, recording its commit (D.50).

GROUNDED. Copier reads copier.yml at the template root; `_exclude` keeps files out of
every generated project, and a template rendering `{{ _copier_conf.answers_file }}`
gives each project a .copier-answers.yml whose `_commit` names the template commit it
came from -- the provenance `copier update` merges against.

A REAL TEMPLATE REPOSITORY, BUILT LOCALLY: this repository's own copier.yml and answers
template, beside a platform file and coursework, committed to a scratch repository.
C.20's isolation keeps these git calls, and Copier's own, off this one.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from copier import run_copy

from nonvacuous import nonempty

REPO = Path(__file__).resolve().parent.parent
ANSWERS_TEMPLATE = "{{ _copier_conf.answers_file }}.jinja"
TEMPLATE_FILES = ("copier.yml", ANSWERS_TEMPLATE)
PLATFORM = "mise.toml"
COURSEWORK = (
    "assignments/assignment-01/notebooks/assignment_01_spark_api.py",
    "resources/assignment_01_job.yml",
    "tests/test_assignment_02.py",
)
SOURCE_PLAN = ("context/plan.toml", "context/plan-ids.toml", "context/plan-trace.toml")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _template(tmp_path: Path) -> tuple[Path, str]:
    """A scratch template repository, committed; it and its commit."""
    for name in nonempty(TEMPLATE_FILES):
        assert (REPO / name).is_file(), f"{name} missing: not yet a Copier template"
    for name in (PLATFORM, *SOURCE_PLAN):
        assert (REPO / name).is_file(), f"{name} missing: the fixture names a file not here"
    source = tmp_path / "template"
    for name in (*TEMPLATE_FILES, PLATFORM, *SOURCE_PLAN):
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / name, source / name)
    # THIS REPOSITORY HOLDS NO COURSEWORK, so the fixture writes it: each path is one that
    # copier.yml excludes, and the proof is that none reaches a generated project (A.121).
    for name in COURSEWORK:
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        (source / name).write_text("coursework\n", encoding="utf-8")
    _git(source, "init", "-q", "-b", "main")
    _git(source, "add", "-A")
    _git(source, "commit", "-q", "-m", "template")
    return source, _git(source, "rev-parse", "HEAD")


def _generate(tmp_path: Path) -> tuple[Path, str]:
    source, commit = _template(tmp_path)
    project = tmp_path / "project"
    run_copy(str(source), project, vcs_ref="HEAD", defaults=True, quiet=True)
    return project, commit


@pytest.mark.usefixtures("platformdirs_isolated")
def test_generated_project_records_its_template_commit(tmp_path: Path) -> None:
    project, commit = _generate(tmp_path)
    answers = (project / ".copier-answers.yml").read_text(encoding="utf-8").splitlines()
    recorded = [line for line in answers if line.startswith("_commit: ")]
    assert len(recorded) == 1, answers
    assert commit[:7] in recorded[0], (commit, recorded)


@pytest.mark.usefixtures("platformdirs_isolated")
def test_generated_project_carries_no_coursework(tmp_path: Path) -> None:
    project, _ = _generate(tmp_path)
    assert (project / PLATFORM).is_file()
    carried = [name for name in COURSEWORK if (project / name).exists()]
    assert carried == []


@pytest.mark.usefixtures("platformdirs_isolated")
def test_generated_project_carries_no_plan_of_its_source(tmp_path: Path) -> None:
    """A generated project starts its own plan; this repository's history is not it (D.53)."""
    project, _ = _generate(tmp_path)
    assert [name for name in SOURCE_PLAN if (project / name).exists()] == []
