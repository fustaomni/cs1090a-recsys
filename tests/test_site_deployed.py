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


def _identity(root: Path) -> None:
    """A declared Railway identity in a scratch root, so nothing reaches the real service."""
    (root / "contracts").mkdir(parents=True, exist_ok=True)
    (root / "site").mkdir(exist_ok=True)
    (root / "contracts" / "site-railway.toml").write_text(
        'contract = "site-railway/v1"\nproject = "p"\nenvironment = "e"\nservice = "s"\n'
        'domain = "d"\n',
        encoding="utf-8",
    )


def test_a_record_names_the_commit_its_deploy_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commit made between site:deploy and site:record is never named as built (A.258)."""
    import subprocess

    import site_deployed

    _identity(tmp_path)
    built, later = "a" * 40, "b" * 40
    monkeypatch.setattr(site_deployed, "built_from", lambda root: built)
    monkeypatch.setattr(
        site_deployed.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0),
    )
    assert site_deployed.deploy(tmp_path) == 0
    monkeypatch.setattr(site_deployed, "built_from", lambda root: later)
    listed = site_deployed.Listed(id="d", status="SUCCESS")
    monkeypatch.setattr(site_deployed, "settled", lambda root: listed)
    monkeypatch.setattr(site_deployed, "counts", lambda root: (14, 12))
    out = tmp_path / ".artifacts" / "spec.toml"
    assert site_deployed.record(out, tmp_path) == 0
    written = out.read_text(encoding="utf-8")
    assert built in written and later not in written, written


def test_an_out_naming_the_record_itself_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--out takes the spec's path; the record's own path is refused before anything is read."""
    import site_deployed

    _identity(tmp_path)
    record = tmp_path / "contracts" / "site-deployment.json"
    record.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(site_deployed, "observed", lambda root: pytest.fail("observed first"))
    with pytest.raises(SystemExit, match="record itself"):
        site_deployed.record(record, tmp_path)
    assert record.read_text(encoding="utf-8") == "{}\n"
