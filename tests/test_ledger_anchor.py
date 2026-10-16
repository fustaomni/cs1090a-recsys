"""The ledger anchor moves only forward, never past an anchor that no longer holds (A.87).

Advancing over a broken anchor would launder the truncation it exposes, so ledger:anchor refuses.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import ledger_anchor
from command_outcome import CommandOutcome
from run_ledger import ANCHOR, append

PROBE: dict[str, object] = {
    "command": "probe",
    "outcome": "success",
    "code": "probed",
    "message": "probed",
    "data": {},
}


def _append(ledger: Path, count: int) -> None:
    for _ in range(count):
        append(CommandOutcome.model_validate(PROBE), ledger=ledger, signer=None)


def _apply(root: Path, spec: str) -> None:
    for op in tomllib.loads(spec)["operations"]:
        target = root / op["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if op["op"] == "create":
            target.write_text(op["content"], encoding="utf-8")
        else:
            text = target.read_text(encoding="utf-8")
            target.write_text(text.replace(op["anchor"], op["replacement"]), encoding="utf-8")


def test_an_anchor_never_moves_past_a_broken_one(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    _append(ledger, 2)
    _apply(tmp_path, ledger_anchor.plan(tmp_path, ledger))
    _append(ledger, 1)
    _apply(tmp_path, ledger_anchor.plan(tmp_path, ledger))
    assert "position = 3" in (tmp_path / ANCHOR).read_text(encoding="utf-8")
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    ledger.write_text("".join(lines[:2]), encoding="utf-8")
    with pytest.raises(SystemExit, match="no longer holds"):
        ledger_anchor.plan(tmp_path, ledger)
