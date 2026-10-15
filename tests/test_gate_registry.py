# tests/test_gate_registry.py
"""Every gate in the registry resolves in this repository (recsys founding F7, plan A.3).

check_all.py was ported with cscie103's whole registry: twenty gates named a script, task or
tool recsys does not have, so the pre-push gate failed closed on gates that could never run. A
gate resolves when its script exists, its mise task is declared, or its executable is uv, mise
or a tool mise.toml pins. A withdrawn gate is named beside GATES, never skipped.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from check_all import GATES, GateSpec

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
