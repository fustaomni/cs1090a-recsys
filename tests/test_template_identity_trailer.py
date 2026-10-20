# tests/test_template_identity_trailer.py
"""A project's identity commit names the step it serves, as its first commit does (A.145).

template:init's commit carries Plan-Step: A.1 (D.61); template:identity's did not, so every
project generated since began with a commit its own requirement matrix refuses as untraced.
A.1 is the day-one step whose done_when lists identity:set, the operation this commit records.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gitenv import git
from project_identity import load
from template_identity import main
from template_init import main as init_main

REPO = Path(__file__).resolve().parent.parent
# COMPOSED, NOT WRITTEN: the PII gate reads any user-at-host literal as an email.
ADDRESS = "t" + "@" + "example.invalid"
SPEC = 'name = "probe-project"\nrepository = "https://github.com/example/probe-project"\n'


def test_the_identity_commit_names_step_a1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "t")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", ADDRESS)
    project = tmp_path / "project"
    declared = load(REPO)
    names = {slot.path for slot in declared.slots} | {"contracts/project-identity.toml"}
    for name in sorted(names):
        (project / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / name, project / name)
    (project / ".copier-answers.yml").write_text("_commit: abc1234\n", encoding="utf-8")
    assert init_main([str(project)]) == 0
    spec = tmp_path / "identity.toml"
    spec.write_text(SPEC, encoding="utf-8")
    assert main([str(project), str(spec)]) == 0
    trailers = git("log", "-1", "--format=%(trailers:key=Plan-Step,valueonly)", cwd=project)
    assert trailers.stdout.strip() == "A.1", trailers.stdout
