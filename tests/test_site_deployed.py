# tests/test_site_deployed.py
"""The live project site is develop's, shown by its recorded deployment (A.254).

site:deploy uploads site/ with railway up, so Railway never learns which commit it was built from;
the deployment is recorded at deploy time instead, as an observation, and this proof reads it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitenv import git

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "contracts" / "site-deployment.json"
PROJECT = ROOT / "site" / "src" / "data" / "project.json"


def test_the_recorded_deployment_names_its_commit_and_carries_fourteen_models_and_twelve_techniques(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    assert RECORD.is_file(), "no deployment has been recorded"
    record: dict[str, object] = json.loads(RECORD.read_text(encoding="utf-8"))
    project: dict[str, object] = json.loads(PROJECT.read_text(encoding="utf-8"))
    models, techniques = project["models"], project["techniques"]
    assert isinstance(models, list) and isinstance(techniques, list), project.keys()
    assert record["contract"] == "site-deployment/v1", record
    assert record["status"] == "SUCCESS", record
    assert isinstance(record["deployment"], str) and record["deployment"], record
    assert (record["models"], record["techniques"]) == (14, 12), record
    assert (record["models"], record["techniques"]) == (len(models), len(techniques)), record
    commit = record["commit"]
    assert isinstance(commit, str), record
    held = git("merge-base", "--is-ancestor", commit, "HEAD", cwd=ROOT)
    assert held.returncode == 0, f"{commit} is not in this branch's history"
