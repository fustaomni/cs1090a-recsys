"""An edited or reordered run record breaks the ledger's hash chain (A.41)."""

from __future__ import annotations

from pathlib import Path

from command_outcome import CommandOutcome
from run_ledger import append, verify


def _outcome(n: int) -> CommandOutcome:
    return CommandOutcome.model_validate(
        {
            "command": "probe",
            "outcome": "success",
            "code": "probe_ran",
            "message": f"run {n}",
            "data": {},
        }
    )


def test_an_edited_or_reordered_run_record_breaks_the_chain(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    for n in range(3):
        append(_outcome(n), ledger=ledger, signer=None)
    assert verify(ledger).intact
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    edited = tmp_path / "edited.jsonl"
    edited.write_text("".join(lines).replace("run 1", "run 9"), encoding="utf-8")
    assert not verify(edited).intact
    reordered = tmp_path / "reordered.jsonl"
    reordered.write_text(lines[0] + lines[2] + lines[1], encoding="utf-8")
    assert not verify(reordered).intact
