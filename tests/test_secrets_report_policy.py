# tests/test_secrets_report_policy.py
"""runs.secrets_report refuses when no scan is supplied, never reading it as clean (A.321).

The ported proofs reach the policy through secrets:report, which always supplies its scan, so this
proof evaluates the policy without one, as the other tasks' absent-request proofs do.
"""

from __future__ import annotations

import secrets_report
import spine


def test_an_absent_scan_is_refused_by_the_policy() -> None:
    evidence = secrets_report.SecretsScan(findings=())
    found = spine.evaluate(
        evidence, "not_secrets_report", secrets_report.POLICY, secrets_report.ENTRYPOINT
    )
    codes = {rule.code for rule in found.rules if rule.outcome == "fail"}
    assert "ERR_SECRETS_SCAN_INPUT_MISSING" in codes, found
