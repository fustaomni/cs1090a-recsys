# tests/test_founding_policy.py
"""The founding policy's pins have one source (plan A.7).

The pinned versions were written three times: in mise_config.rego, in its test's input, and
in mise.toml, so A.4 edited all three in lock-step and a missed one would have let the policy
and its own test disagree silently. policies/founding/data.json now holds them once; the policy
and its test read it, and this test proves it agrees with mise.toml and mise.lock, that no
pinned version is restated in the policy, and that the policy still judges by it.
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOUNDING = ROOT / "policies" / "founding"


def _pins() -> dict[str, object]:
    pins = json.loads((FOUNDING / "data.json").read_text(encoding="utf-8"))["founding"]["pins"]
    assert isinstance(pins, dict), pins
    return pins


def _config() -> dict[str, object]:
    return tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))


def _allow(config: dict[str, object], tmp_path: Path) -> str:
    given = tmp_path / "input.json"
    given.write_text(json.dumps(config), encoding="utf-8")
    done = subprocess.run(
        [
            "opa",
            "eval",
            "--format",
            "raw",
            "-d",
            str(FOUNDING),
            "-i",
            str(given),
            "data.founding.mise.allow",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_the_policy_pins_are_the_lockfile_pins() -> None:
    tools = _pins()["tools"]
    assert isinstance(tools, dict) and tools, tools
    declared = _config()["tools"]
    assert isinstance(declared, dict), declared
    locked = tomllib.loads((ROOT / "mise.lock").read_text(encoding="utf-8"))["tools"]
    assert tools == {name: str(version) for name, version in declared.items()}
    assert tools == {name: entries[0]["version"] for name, entries in locked.items()}
    rego = (FOUNDING / "mise_config.rego").read_text(encoding="utf-8")
    restated = sorted(version for version in tools.values() if f'"{version}"' in rego)
    assert not restated, "a pinned version is restated in the policy: " + ", ".join(restated)


def test_the_policy_judges_by_the_pins(tmp_path: Path) -> None:
    config = _config()
    assert _allow(config, tmp_path) == "true"
    tools = config["tools"]
    assert isinstance(tools, dict), tools
    drifted = {**config, "tools": {**tools, next(iter(tools)): "0.0.0"}}
    assert _allow(drifted, tmp_path) == "false"
