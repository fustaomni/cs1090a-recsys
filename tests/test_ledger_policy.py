"""The ledger's policy refuses a broken chain by its own rule, not only through verify (A.86).

verify reports whether the chain holds; runs.ledger decides. A proof that reads only verify's
flag would pass with the policy's rule disabled, so this one asks the policy for its code.
"""

from __future__ import annotations

import spine
from run_ledger import ENTRYPOINT, POLICY, SUBJECT, LedgerReport


def test_a_broken_chain_is_refused_by_the_policy() -> None:
    report = LedgerReport(
        ledger="ledger.jsonl", records=2, intact=False, broken_at=2, tasks=("probe",)
    )
    found = spine.evaluate(report, SUBJECT, POLICY, ENTRYPOINT)
    codes = {rule.code for rule in found.rules if rule.outcome == "fail"}
    assert "ERR_LEDGER_CHAIN_BROKEN" in codes, found
