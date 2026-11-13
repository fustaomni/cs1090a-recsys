# tests/test_safeguard_mutants.py
"""Every policy safeguard's mutant compiles, so its trial judges the guard, not a crash (A.325).

DATA.MEMBER_UNSAFE replaced a rule's only binding of a name with false; the module stopped
compiling, every opa eval over policies failed, and safeguards:prove could only call the trial
inconclusive. A mutant that does not compile is invalid, never a kill, so each is checked here.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "contracts" / "safeguards.toml"


def _policy_safeguards() -> list[dict[str, str]]:
    entries = tomllib.loads(REGISTER.read_text(encoding="utf-8"))["safeguards"]
    return [entry for entry in entries if str(entry["path"]).endswith(".rego")]


def test_every_policy_safeguard_mutant_compiles(tmp_path: Path) -> None:
    safeguards = _policy_safeguards()
    shutil.copytree(ROOT / "policies", tmp_path / "policies")
    failures: list[str] = []
    for entry in nonempty(safeguards):
        target = tmp_path / entry["path"]
        original = target.read_text(encoding="utf-8")
        assert original.count(entry["anchor"]) == 1, entry["id"]
        target.write_text(original.replace(entry["anchor"], entry["mutant"]), encoding="utf-8")
        checked = subprocess.run(
            ["opa", "check", str(tmp_path / "policies")],
            capture_output=True,
            text=True,
            check=False,
        )
        target.write_text(original, encoding="utf-8")
        if checked.returncode != 0:
            said = (checked.stderr or checked.stdout).strip().splitlines()
            failures.append(f"{entry['id']}: {said[0] if said else 'opa check failed'}")
    assert failures == [], failures
