# tests/test_gate_registry.py
"""Every gate in the registry resolves in this repository (recsys founding F7, plan A.3).

check_all.py was ported with cscie103's whole registry: twenty gates named a script, task or
tool recsys does not have, so the pre-push gate failed closed on gates that could never run. A
gate resolves when its script exists, its mise task is declared, or its executable is uv, mise
or a tool mise.toml pins. A withdrawn gate is named beside GATES, never skipped.
"""

from __future__ import annotations

import secrets
import string
import subprocess
import tomllib
from pathlib import Path

from check_all import GATES, GateSpec
from gitenv import scrubbed_env

ROOT = Path(__file__).resolve().parent.parent
CONFIG = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
LAUNCHERS = frozenset({"uv", "mise"})


def _unresolved(spec: GateSpec) -> str | None:
    command = list(spec.command)
    scripts = [part for part in command if part.startswith("scripts/") and part.endswith(".py")]
    if scripts and not (ROOT / scripts[0]).is_file():
        return scripts[0]
    if command[:2] == ["mise", "run"]:
        task = next(part for part in command[2:] if not part.startswith("-"))
        if task not in CONFIG["tasks"]:
            return "task " + task
    tools = {str(name).split(":")[-1] for name in CONFIG.get("tools", {})}
    if command[0] not in LAUNCHERS | tools:
        return "executable " + command[0]
    return None


def test_every_gate_resolves_in_this_repository() -> None:
    assert GATES, "the registry is empty: nothing would be gated"
    unresolved = sorted(f"{spec.name} ({what})" for spec in GATES if (what := _unresolved(spec)))
    assert not unresolved, "gates that do not resolve here: " + "; ".join(unresolved)


def test_an_unresolvable_gate_is_named() -> None:
    """The paired negative control: the rule names what it cannot resolve."""
    script = GATES[0].model_copy(
        update={"name": "planted", "command": ("uv", "run", "python", "scripts/absent.py")}
    )
    tool = GATES[0].model_copy(update={"name": "planted", "command": ("absent-tool", "scan")})
    assert _unresolved(script) == "scripts/absent.py"
    assert _unresolved(tool) == "executable absent-tool"


def test_the_history_is_scanned_for_secrets(tmp_path: Path) -> None:
    """A.4: the hooks scan the whole history, and the scan bites on a commit, not only a file.

    tests/test_secret_scanning.py (ported) proves betterleaks on a directory. This proves the
    gate as registered: its own command, on a scratch repository whose history holds a canary
    generated per run, so no credential-shaped literal is ever committed here.
    """
    gates = [spec for spec in GATES if spec.name == "secrets (history)"]
    assert gates, "no secrets (history) gate: the history is not scanned"
    (gate,) = gates
    assert gate.runs_in_hooks and gate.command[:2] == ("betterleaks", "git"), gate
    canary = "ghp_" + "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(36)
    )
    (tmp_path / "config.txt").write_text(f'token = "{canary}"\n', encoding="utf-8")
    identity = (
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "-c",
        "commit.gpgsign=false",
    )
    for args in (("init", "-q"), ("add", "config.txt"), ("commit", "-q", "-m", "canary")):
        subprocess.run(["git", *identity, *args], cwd=tmp_path, env=scrubbed_env(), check=True)
    done = subprocess.run(
        [*gate.command, str(tmp_path)], capture_output=True, text=True, check=False
    )
    assert done.returncode != 0, "the history scan reported clean on a committed credential"
    assert canary not in done.stdout + done.stderr, "the secret appeared verbatim in scanner output"
