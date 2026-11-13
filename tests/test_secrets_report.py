# tests/test_secrets_report.py
"""secrets:report names each history finding by its fingerprint, on the spine (D.465).

cs1090a-recsys's secrets (history) gate failed with one leak and no detail, because betterleaks
ran with --redact and no report. This reads the redacted JSON report instead: a finding is
refused by its fingerprint, the evidence never carries a secret, match, author or email, and a
scan that failed, contradicted itself or answered in another shape halts, never passes.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

import pytest

Scanner = Callable[[Sequence[str]], tuple[int, str]]

COMMIT = "0a1b2c3d4e5f60718293a4b5c6d7e8f901234567"
FINGERPRINT = f"{COMMIT}:notebooks/demo.py:generic-api-key:12"
FINDING = {
    "RuleID": "generic-api-key",
    "Description": "Generic API Key",
    "File": "notebooks/demo.py",
    "StartLine": 12,
    "EndLine": 12,
    "Commit": COMMIT,
    "Fingerprint": FINGERPRINT,
    "Match": "MATCH-MARKER",
    "Secret": "SECRET-MARKER",
    "Author": "AUTHOR-MARKER",
    "Email": "email-marker@example.invalid",
}


def _scanner(code: int, out: str, calls: list[tuple[str, ...]] | None = None) -> Scanner:
    """betterleaks answering with an exit code and its report, recording what it was asked."""

    def scan(args: Sequence[str]) -> tuple[int, str]:
        if calls is not None:
            calls.append(tuple(args))
        return code, out

    return scan


def test_a_clean_history_is_verified(capsys: pytest.CaptureFixture[str]) -> None:
    from secrets_report import main

    code = main(scan=_scanner(0, "[]"))
    outcome = json.loads(capsys.readouterr().out)
    assert code == 0, outcome
    assert outcome["code"] == "secrets_verified", outcome


def test_a_finding_is_refused_by_its_fingerprint(capsys: pytest.CaptureFixture[str]) -> None:
    from secrets_report import main

    code = main(scan=_scanner(1, json.dumps([FINDING])))
    outcome = json.loads(capsys.readouterr().out)
    assert code != 0, outcome
    assert outcome["code"] == "secrets_refused", outcome
    assert "[ERR_SECRETS_FOUND]" in outcome["message"], outcome
    assert FINGERPRINT in outcome["message"], outcome


def test_the_evidence_never_carries_a_secret_match_author_or_email(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from secrets_report import main

    main(scan=_scanner(1, json.dumps([FINDING])))
    printed = capsys.readouterr().out
    assert FINGERPRINT in printed, printed
    for marker in ("MATCH-MARKER", "SECRET-MARKER", "AUTHOR-MARKER", "email-marker@"):
        assert marker not in printed, marker


def test_a_failed_scanner_halts(capsys: pytest.CaptureFixture[str]) -> None:
    from secrets_report import main

    code = main(scan=_scanner(126, ""))
    outcome = json.loads(capsys.readouterr().out)
    assert code != 0, outcome
    assert outcome["code"] == "secrets_unscanned", outcome


def test_an_exit_its_findings_contradict_halts(capsys: pytest.CaptureFixture[str]) -> None:
    from secrets_report import main

    code = main(scan=_scanner(0, json.dumps([FINDING])))
    outcome = json.loads(capsys.readouterr().out)
    assert code != 0, outcome
    assert outcome["code"] == "secrets_unscanned", outcome


def test_a_reshaped_report_halts(capsys: pytest.CaptureFixture[str]) -> None:
    from secrets_report import main

    code = main(scan=_scanner(1, json.dumps({"findings": "not a list"})))
    outcome = json.loads(capsys.readouterr().out)
    assert code != 0, outcome
    assert outcome["code"] == "secrets_unscanned", outcome


def test_the_scan_is_redacted_and_writes_a_json_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from secrets_report import main

    calls: list[tuple[str, ...]] = []
    main(scan=_scanner(0, "[]", calls))
    capsys.readouterr()
    assert len(calls) == 1, calls
    asked = calls[0]
    assert asked[:2] == ("betterleaks", "git"), asked
    assert "--redact" in asked, asked
    assert "--report-format=json" in asked, asked
    assert [arg for arg in asked if arg.startswith("--report-path=")], asked
