# tests/test_site_deployed.py
"""The live project site is develop's, shown by its recorded deployment (A.254).

site:deploy uploads site/ with railway up, so Railway never learns which commit it was built from;
the deployment is recorded at deploy time instead, as an observation, and this proof reads it.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from gitenv import git

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "contracts" / "site-deployment.json"
PROJECT = ROOT / "site" / "src" / "data" / "project.json"
IDENTITY = ROOT / "contracts" / "site-railway.toml"


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
    assert IDENTITY.is_file(), "no declared Railway identity"
    identity: dict[str, object] = tomllib.loads(IDENTITY.read_text(encoding="utf-8"))
    declared = (identity["project"], identity["service"])
    assert (record["project"], record["service"]) == declared, record


def test_a_generated_project_carries_no_railway_identity_or_deployment() -> None:
    """This project's deployment facts are its own: copier.yml keeps them out (A.254)."""
    import fnmatch

    import yaml

    loaded = yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "copier.yml is not a mapping"
    excluded = [str(pattern) for pattern in loaded.get("_exclude", [])]
    own = ("contracts/site-railway.toml", "contracts/site-deployment.json")
    for path in (*own, "tests/test_site_deployed.py"):
        assert any(fnmatch.fnmatch(path, pattern) for pattern in excluded), path


def test_site_deploy_targets_only_the_declared_railway_identity() -> None:
    """site:deploy passes the declared ids and can never create a project (A.254)."""
    assert IDENTITY.is_file(), "no declared Railway identity"
    identity: dict[str, object] = tomllib.loads(IDENTITY.read_text(encoding="utf-8"))
    import site_deployed

    command = site_deployed.up_command(site_deployed.declared())
    for flag in ("project", "environment", "service"):
        assert f"--{flag}" in command, command
        assert command[command.index(f"--{flag}") + 1] == identity[flag], command
    assert "-y" not in command and "--yes" not in command and "--name" not in command, command
