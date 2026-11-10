# scripts/site_deployed.py
"""site:record deployment -- the live site's deployment recorded as an observation (A.254).

site:deploy uploads site/ with railway up, so Railway never learns which commit it was built from.
site:deploy notes that commit from a site/ with no uncommitted change before it uploads, and
the recorder takes that note (A.258), the newest deployment
Railway lists, waited on until its status is final, and the model and technique counts the deployed
data carries, then emits a source-apply spec writing contracts/site-deployment.json. Only a SUCCESS
is recorded; a failed or crashed deployment is refused by name.
"""

from __future__ import annotations

import json
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field

from contract_base import Contract, from_document
from gitenv import git

ROOT = Path(__file__).resolve().parent.parent
RECORD = Path("contracts") / "site-deployment.json"
MARKER = Path(".artifacts") / "site-deploy-commit"
PROJECT = Path("site") / "src" / "data" / "project.json"
QUOTE = "'" * 3
COMMIT = r"^[0-9a-f]{40}$"
# FINAL STATUSES, as the Railway CLI's DeploymentOutput names them; any other is still in flight.
FINAL = frozenset({"SUCCESS", "FAILED", "CRASHED", "REMOVED", "SKIPPED"})
POLL_SECONDS = 10.0
DEADLINE_SECONDS = 900.0
IDENTITY = Path("contracts") / "site-railway.toml"
# A.273: THE SITE'S OWN @railway/cli, BY ITS npm SCRIPT; npx could resolve railway to the IaC SDK.
CLI = ("mise", "exec", "node@24", "--", "npm", "run", "--silent", "railway", "--")


class Listed(Contract):
    """The newest deployment as railway deployment list --json reports it: its id and status."""

    id: str = Field(min_length=1)
    status: str = Field(min_length=1)


class Identity(Contract):
    """site-railway/v1: the Railway project, environment and service that serve the live site."""

    contract: Literal["site-railway/v1"] = "site-railway/v1"
    project: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    service: str = Field(min_length=1)
    domain: str = Field(min_length=1)


def declared(root: Path = ROOT) -> Identity:
    """The site's declared Railway identity, validated."""
    return from_document(Identity, tomllib.loads((root / IDENTITY).read_text(encoding="utf-8")))


def _target(identity: Identity) -> list[str]:
    """The ids every Railway command names, so none falls back to a directory's link."""
    return [
        "--project",
        identity.project,
        "--environment",
        identity.environment,
        "--service",
        identity.service,
    ]


def up_command(identity: Identity) -> list[str]:
    """railway up to the declared service only: no -y and no --name, so it never creates one."""
    return [*CLI, "up", "--detach", *_target(identity)]


def link_command(identity: Identity) -> list[str]:
    """railway link to the declared ids, non-interactively (A.273)."""
    return [*CLI, "link", *_target(identity)]


def link(root: Path = ROOT) -> int:
    """Link this checkout's site/ to the declared service: config commands read only the link."""
    return subprocess.run(link_command(declared(root)), cwd=root / "site", check=False).returncode


def deploy(root: Path = ROOT) -> int:
    """Upload site/ to the declared service, noting the commit it was built from (A.258).

    THE COMMIT IS READ BEFORE THE UPLOAD, so a commit made before site:record is never named.
    """
    commit = built_from(root)
    code = subprocess.run(up_command(declared(root)), cwd=root / "site", check=False).returncode
    if code == 0:
        marker = root / MARKER
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(commit + "\n", encoding="utf-8")
    return code


def delete_project(project: str, root: Path = ROOT) -> int:
    """Delete a project an unlinked deploy created, by its id only; never the declared one."""
    if project == declared(root).project:
        raise SystemExit(f"{project} is the site's declared project, which is never deleted")
    command = [*CLI, "delete", "--project", project, "--yes", "--json"]
    return subprocess.run(command, cwd=root / "site", check=False).returncode


class Deployment(Contract):
    """site-deployment/v1: the live site's deployment, observed, with no verdict of its own."""

    contract: Literal["site-deployment/v1"] = "site-deployment/v1"
    commit: str = Field(pattern=COMMIT)
    deployment: str = Field(min_length=1)
    project: str = Field(min_length=1)
    service: str = Field(min_length=1)
    status: Literal["SUCCESS"]
    models: int = Field(ge=0)
    techniques: int = Field(ge=0)


def built_from(root: Path = ROOT) -> str:
    """HEAD, once site/ is exactly what HEAD holds, since railway up uploads it as it stands."""
    changed = git("status", "--porcelain", "--", "site", cwd=root).stdout.strip()
    if changed:
        raise SystemExit(f"site/ holds uncommitted changes, so no commit names it:\n{changed}")
    return git("rev-parse", "HEAD", cwd=root).stdout.strip()


def counts(root: Path = ROOT) -> tuple[int, int]:
    """The number of models and techniques the site's data carries."""
    project = json.loads((root / PROJECT).read_text(encoding="utf-8"))
    models, techniques = project.get("models"), project.get("techniques")
    if not isinstance(models, list) or not isinstance(techniques, list):
        raise SystemExit(f"{PROJECT} holds no models and techniques lists")
    return len(models), len(techniques)


def newest(root: Path = ROOT) -> Listed:
    """The newest deployment of the linked service, as Railway lists it."""
    listed = subprocess.run(
        [*CLI, "deployment", "list", *_target(declared(root)), "--json", "--limit", "1"],
        cwd=root / "site",
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode != 0:
        raise SystemExit(f"railway deployment list exited {listed.returncode}: {listed.stderr}")
    entries = json.loads(listed.stdout)
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        raise SystemExit("railway deployment list reported no deployment")
    first = entries[0]
    return from_document(Listed, {"id": first.get("id"), "status": first.get("status")})


def settled(root: Path = ROOT) -> Listed:
    """The newest deployment once its status is final, within the deadline."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    while True:
        seen = newest(root)
        if seen.status in FINAL:
            return seen
        if time.monotonic() >= deadline:
            raise SystemExit(f"deployment {seen.id} still {seen.status} after {DEADLINE_SECONDS}s")
        time.sleep(POLL_SECONDS)


def deployed_commit(root: Path = ROOT) -> str:
    """The commit the last site:deploy built from, as it noted it."""
    marker = root / MARKER
    if not marker.is_file():
        raise SystemExit(f"no site:deploy noted the commit it built ({MARKER}); deploy first")
    return marker.read_text(encoding="utf-8").strip()


def observed(root: Path = ROOT) -> Deployment:
    """The deployment record, refused unless the deployment succeeded."""
    commit = deployed_commit(root)
    final = settled(root)
    if final.status != "SUCCESS":
        raise SystemExit(f"deployment {final.id} ended {final.status}, so nothing is recorded")
    models, techniques = counts(root)
    identity = declared(root)
    return Deployment(
        commit=commit,
        deployment=final.id,
        project=identity.project,
        service=identity.service,
        status="SUCCESS",
        models=models,
        techniques=techniques,
    )


def render(deployment: Deployment) -> str:
    """The record as committed: indented JSON, one trailing newline."""
    return json.dumps(deployment.model_dump(mode="json"), indent=2) + "\n"


def spec(current: str | None, text: str) -> str:
    """A source-apply spec that creates the record, or replaces it whole."""
    target = f'path = "{RECORD.as_posix()}"\n'
    if current is None:
        head = 'contract = "source-apply/v1"\n\n[[operations]]\nop = "create"\n'
        return head + target + f"content = {QUOTE}{text}{QUOTE}\n"
    head = 'contract = "source-apply/v1"\n\n[[operations]]\nop = "replace"\n'
    body = f"anchor = {QUOTE}{current}{QUOTE}\nreplacement = {QUOTE}{text}{QUOTE}\n"
    return head + target + body


def record(out: Path, root: Path = ROOT) -> int:
    """Observe the deployment and write the spec that records it at out."""
    if out.resolve() == (root / RECORD).resolve():
        raise SystemExit("--out names the record itself; give a spec path, then apply it")
    deployment = observed(root)
    existing = root / RECORD
    current = existing.read_text(encoding="utf-8") if existing.is_file() else None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(spec(current, render(deployment)), encoding="utf-8")
    print(f"recorded deployment {deployment.deployment} of {deployment.commit[:12]}; apply {out}")
    return 0
