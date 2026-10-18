"""The ledger's policy refuses a broken chain by its own rule, not only through verify (A.86).

verify reports whether the chain holds; runs.ledger decides. A proof that reads only verify's
flag would pass with the policy's rule disabled, so this one asks the policy for its code.
"""

from __future__ import annotations

from pathlib import Path

import spine
from command_outcome import CommandOutcome
from run_ledger import (
    ENTRYPOINT,
    POLICY,
    SUBJECT,
    LedgerAnchor,
    LedgerReport,
    RunRecord,
    append,
    verify,
)

PROBE: dict[str, object] = {
    "command": "probe",
    "outcome": "success",
    "code": "probed",
    "message": "probed",
    "data": {},
}


def _ledger(tmp_path: Path, count: int) -> Path:
    ledger = tmp_path / "ledger.jsonl"
    for _ in range(count):
        append(CommandOutcome.model_validate(PROBE), ledger=ledger, signer=None)
    return ledger


def _anchor(ledger: Path, position: int) -> LedgerAnchor:
    lines = ledger.read_text(encoding="utf-8").splitlines()
    record = RunRecord.model_validate_json(lines[position - 1])
    return LedgerAnchor(
        ledger=str(ledger), position=position, run_id=record.run_id, sha256=record.sha256
    )


def _cut(ledger: Path, keep: int) -> None:
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    ledger.write_text("".join(lines[:keep]), encoding="utf-8")


def _codes_of(report: LedgerReport) -> set[str]:
    found = spine.evaluate(report, SUBJECT, POLICY, ENTRYPOINT)
    return {rule.code for rule in found.rules if rule.outcome == "fail"}


def test_a_broken_chain_is_refused_by_the_policy() -> None:
    report = LedgerReport(
        ledger="ledger.jsonl", records=2, intact=False, broken_at=2, tasks=("probe",)
    )
    found = spine.evaluate(report, SUBJECT, POLICY, ENTRYPOINT)
    codes = {rule.code for rule in found.rules if rule.outcome == "fail"}
    assert "ERR_LEDGER_CHAIN_BROKEN" in codes, found


def test_a_truncated_ledger_is_refused(tmp_path: Path) -> None:
    """Cutting the newest record leaves a valid, shorter chain; only the anchor sees it."""
    ledger = _ledger(tmp_path, 3)
    anchor = _anchor(ledger, 3)
    assert not verify(ledger, anchor=anchor).anchor_broken
    _cut(ledger, 2)
    report = verify(ledger, anchor=anchor)
    assert report.intact and report.anchor_broken
    assert "ERR_LEDGER_ANCHOR_BROKEN" in _codes_of(report)


def test_a_refilled_tail_is_refused(tmp_path: Path) -> None:
    """A cut tail written over with new records holds its length but not the anchored record."""
    ledger = _ledger(tmp_path, 3)
    anchor = _anchor(ledger, 3)
    _cut(ledger, 2)
    _ledger(tmp_path, 1)
    report = verify(ledger, anchor=anchor)
    assert (report.intact, report.records, report.anchor_broken) == (True, 3, True)
    assert "ERR_LEDGER_ANCHOR_BROKEN" in _codes_of(report)
