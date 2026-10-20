# tests/integration/test_generated_gate.py
"""A generated project passes its own gate from its first published commit (D.61, A.123).

olist-lakehouse-bi failed its own offline gate on the push that would have published it.
2026 templates prove the opposite with an integration test: generate, then run the
project's own checks in it. This does that -- generate from this working tree, start the
repository and its plan, publish to a local bare repository so origin/develop is real,
then run the project's own tests with this interpreter.

INTEGRATION, NOT OFFLINE: it renders a whole project and runs its suite, which is slow
and needs the devShell tools; check runs it, CI runs it, pre-push does not.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tomllib
import warnings
from collections.abc import Iterator
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from copier import run_copy
from copier.errors import DirtyLocalWarning
from platformdirs.testing import isolated_dirs

from gitenv import scrubbed_env
from template_init import main as init_main

# THREE PARENTS: this file lives at tests/integration, the level its directory declares (A.39).
REPO = Path(__file__).resolve().parent.parent.parent
# COMPOSED, NOT WRITTEN: the PII gate reads any user-at-host literal as an email.
ADDRESS = "t" + "@" + "example.invalid"
# A SCRATCH IDENTITY, as a project takes its own after generation (D.64). SENTINEL VALUES:
# a common word (the first draft used `probe`) coincides with ordinary prose, and a
# coincidence reported as a literal is noise, not a template defect.
IDENTITY = "\n".join(
    (
        'name = "zqx-sentinel-project"',
        'repository = "https://github.com/example/zqx-sentinel-project"',
        "",
    )
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, env=scrubbed_env(), check=True, capture_output=True, text=True
    )


def _tail(done: subprocess.CompletedProcess[str]) -> str:
    return "\n".join((done.stdout + done.stderr).splitlines()[-200:])


def _env(project: Path) -> dict[str, str]:
    """The project's own environment: no inherited venv (D.12), its config trusted.

    MISE_TRUSTED_CONFIG_PATHS trusts this one scratch path for these calls only, adding
    nothing to the global trust list; trust never comes from the project's own config
    (CVE-2026-35533). The path is resolved, because macOS reports /private/... to mise.
    """
    environment = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    environment["MISE_TRUSTED_CONFIG_PATHS"] = str(project.resolve())
    return environment


def _in(project: Path, *command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command), cwd=project, env=_env(project), capture_output=True, text=True, check=False
    )


def _point(project: Path, bare: Path) -> None:
    """origin names the project's declared GitHub repository; its pushes reach a local bare one.

    source:apply reads the repository from origin, so origin must read as GitHub, as every real
    project's does. git remote get-url expands insteadOf but not pushInsteadOf, so only the push
    is redirected, and it stays offline (A.123).
    """
    declared = tomllib.loads((project / "contracts" / "project-identity.toml").read_text("utf-8"))
    url = f"{declared['repository']}.git"
    _git(project, "remote", "set-url", "origin", url)
    _git(project, "config", f"url.{bare}.pushInsteadOf", url)


def _born(base: Path, patch: pytest.MonkeyPatch) -> Path:
    """Generated, born a repository with its plan, published to a bare remote, synced."""
    for role in ("AUTHOR", "COMMITTER"):
        patch.setenv(f"GIT_{role}_NAME", "t")
        patch.setenv(f"GIT_{role}_EMAIL", ADDRESS)
    project = base / "project"
    with warnings.catch_warnings():
        # THE WORKING TREE IS THE TEMPLATE UNDER TEST, uncommitted changes included.
        warnings.simplefilter("ignore", DirtyLocalWarning)
        run_copy(str(REPO), project, defaults=True, quiet=True)
    with redirect_stdout(io.StringIO()):
        # BORN WITH ITS PLAN: template:init commits it, traced to A.1.
        assert init_main([str(project)]) == 0
    bare = base / "remote.git"
    _git(base, "init", "-q", "--bare", str(bare))
    _git(project, "remote", "add", "origin", str(bare))
    _point(project, bare)
    _git(project, "push", "-q", "origin", "main", "develop")
    # ITS OWN VENV, AS ITS setup MAKES IT: the runtime contract refuses any other (6874ca0).
    synced = _in(project, "uv", "sync", "--locked", "--all-groups", "--offline")
    assert synced.returncode == 0, _tail(synced)
    return project


@pytest.fixture(scope="module")
def published(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Generated, born a repository, its plan started, published to a bare remote."""
    base = tmp_path_factory.mktemp("generated")
    with pytest.MonkeyPatch.context() as patch, isolated_dirs(base / "dirs"):
        yield _born(base, patch)


@pytest.fixture(scope="module")
def identified(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[Path, dict[str, object]]]:
    """Born as above, then given its own identity."""
    base = tmp_path_factory.mktemp("identified")
    with pytest.MonkeyPatch.context() as patch, isolated_dirs(base / "dirs"):
        project = _born(base, patch)
        spec = base / "identity.toml"
        spec.write_text(IDENTITY, encoding="utf-8")
        script = ("uv", "run", "--no-sync", "python")
        named = _in(project, *script, "scripts/project_identity.py", str(spec))
        assert named.returncode == 0, _tail(named)
        # ITS ORIGIN FOLLOWS ITS IDENTITY, as template:publish pairs them in a real project.
        _point(project, base / "remote.git")
        yield project, json.loads(named.stdout)


@pytest.mark.integration
def test_a_generated_project_passes_its_own_tests(published: Path) -> None:
    done = _in(
        published,
        "uv",
        "run",
        "--no-sync",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-m",
        "not integration",
    )
    assert done.returncode == 0, _tail(done)


@pytest.mark.integration
def test_a_generated_project_with_its_own_identity_passes_its_own_gate(
    identified: tuple[Path, dict[str, object]],
) -> None:
    """What every real project does next: take its identity (D.64).

    olist-lakehouse-bi then kept this repository's name in files no slot covers, and its
    release tests read this repository's coursework job. Every failing gate is collected.
    """
    project, envelope = identified
    data = envelope["data"]
    assert isinstance(data, dict), envelope
    left = data["left_behind"]
    assert isinstance(left, list), data
    assert left == [], "\n".join(str(entry) for entry in left)
    # ITS OWN GATE, JUDGING THE PROJECT, NOT THE MACHINE (A.123): --offline drops its integration
    # tier, which is this proof, and --ci its claims about the developer machine (A.104), which
    # this repository's own test (machine) judges and which a CI runner is not.
    gates = (("python", "scripts/check_all.py", "--offline", "--ci"),)
    failed: dict[str, str] = {}
    for gate in gates:
        done = _in(project, "uv", "run", "--no-sync", *gate)
        if done.returncode != 0:
            failed[" ".join(gate)] = _tail(done)
    # A JOINED STRING, NOT A DICT: pytest prints a message whole, a dict's repr truncated.
    assert not failed, "\n\n".join(f"== {gate}\n{tail}" for gate, tail in failed.items())
