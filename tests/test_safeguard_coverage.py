"""Every closed code under policies is a registered safeguard (A.89).

A guard is a deny rule with a closed code; the register names the mutation that disables it and
the proof that must then fail. A code with no entry is a guard nobody has shown to work, and an
entry naming no code is a register that has drifted from its policies. Both are refused here.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = re.compile(r"^#   code: (ERR_[A-Z0-9_]+)$", re.MULTILINE)


def _closed_codes() -> set[str]:
    found: set[str] = set()
    for policy in sorted((ROOT / "policies").rglob("*.rego")):
        found |= set(CODE.findall(policy.read_text(encoding="utf-8")))
    return found


def test_every_closed_code_is_a_registered_safeguard() -> None:
    text = (ROOT / "contracts" / "safeguards.toml").read_text(encoding="utf-8")
    guarded = {entry["guard"] for entry in tomllib.loads(text)["safeguards"]}
    codes = _closed_codes()
    assert sorted(codes - guarded) == [], "closed codes with no registered safeguard"
    assert sorted(guarded - codes) == [], "registered guards that no policy holds"
