# scripts/secrets_report.py
"""secrets:report -- each finding in the repository's history named by fingerprint (D.465).

THE GATE'S SUMMARY IS NOT EVIDENCE. The secrets (history) gate runs betterleaks with --redact and
prints only how many leaks it found, so a failing gate cannot be classified. This scan writes
betterleaks' redacted JSON report and reads each finding's rule, file, line, commit and
fingerprint. The secret, the matched text, the author and the email are never declared, so they
never reach the evidence.

A SCAN THAT CANNOT BE JUDGED HALTS. A failed scanner, a report in another shape, or an exit code
its own report contradicts is a halt, never a pass; only a finding is refused.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, TypeAdapter, ValidationError

from command_outcome import announce
from contract_base import Contract, Reading
from nix_remediation import ActionableError
from spine import decide, enforce, evaluate, halted, reasons, refusal_code

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "policies" / "runs" / "secrets_report"
ENTRYPOINT = "data.runs.secrets_report.deny"
SUBJECT = "secrets_report"
COMMAND = "secrets:report"
REPORT_FLAG = "--report-path="
CLEAN = 0
FOUND = 1
# WHAT TO DO, DECLARED WITH EACH WAY A SCAN CANNOT BE JUDGED.
RERUN = "run it where the pinned betterleaks is installed: mise run run secrets:report"
RESHAPED = "betterleaks' JSON changed shape; read its release notes, then update _Finding"

Scanner = Callable[[Sequence[str]], tuple[int, str]]


class ScanIncompleteError(ActionableError):
    """The scan cannot be judged: it failed, answered in another shape, or contradicted itself."""

    code = "ERR_SECRETS_UNSCANNED"


def scan_args(report: Path) -> tuple[str, ...]:
    """The whole history, redacted, with a JSON report written to report."""
    return (
        "betterleaks",
        "git",
        "--redact",
        "--no-banner",
        "--report-format=json",
        f"{REPORT_FLAG}{report}",
    )


def _scan(args: Sequence[str]) -> tuple[int, str]:
    """betterleaks' exit code and the report it wrote; a binary that cannot start is 127."""
    named = next(arg for arg in args if arg.startswith(REPORT_FLAG))
    report = Path(named.removeprefix(REPORT_FLAG))
    try:
        done = subprocess.run(list(args), cwd=ROOT, capture_output=True, text=True, check=False)
    except OSError:
        return 127, ""
    written = report.read_text(encoding="utf-8") if report.is_file() else ""
    return done.returncode, written


class _Finding(Reading):
    """One finding as betterleaks reports it: only the fields that locate it are declared."""

    rule_id: str = Field(alias="RuleID")
    file: str = Field(alias="File")
    line: int = Field(alias="StartLine")
    commit: str = Field(alias="Commit")
    fingerprint: str = Field(alias="Fingerprint")


REPORT = TypeAdapter(tuple[_Finding, ...])


class Finding(Contract):
    """One finding, located by rule, file, line and commit, and named by its fingerprint."""

    rule_id: str
    file: str
    line: int
    commit: str
    fingerprint: str


class SecretsScan(Contract):
    """secrets-scan/v1: every finding betterleaks reported in the repository's history."""

    CONTRACT_ID: ClassVar[str] = "secrets-scan/v1"

    contract: Literal["secrets-scan/v1"] = "secrets-scan/v1"
    findings: tuple[Finding, ...]


def observe(scan: Scanner) -> SecretsScan:
    """The scan as evidence; a scan that cannot be judged is raised, never returned."""
    with tempfile.TemporaryDirectory() as scratch:
        code, out = scan(scan_args(Path(scratch) / "report.json"))
    if code not in (CLEAN, FOUND):
        raise ScanIncompleteError(f"betterleaks exited {code}", remediation=RERUN)
    try:
        reported = REPORT.validate_json(out)
    except ValidationError as error:
        first = str(error).splitlines()[0]
        shape = f"betterleaks answered in another shape: {first}"
        raise ScanIncompleteError(shape, remediation=RESHAPED) from error
    findings = tuple(
        Finding(
            rule_id=found.rule_id,
            file=found.file,
            line=found.line,
            commit=found.commit,
            fingerprint=found.fingerprint,
        )
        for found in reported
    )
    if (code == FOUND) != bool(findings):
        listed = f"listed {len(findings)} finding(s)"
        raise ScanIncompleteError(f"betterleaks exited {code} but {listed}", remediation=RERUN)
    return SecretsScan(findings=findings)


def main(*, scan: Scanner = _scan) -> int:
    """Scan the history, judge what it found, and exit from the decision alone."""
    try:
        state = observe(scan)
    except ScanIncompleteError as incomplete:
        # A SCAN THAT CANNOT BE JUDGED IS A HALT, NOT A PASS: an unread history is not a clean one.
        reason = incomplete.message
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, reason)
        detail = {"decision": stopped.model_dump(mode="json"), "error": incomplete.as_dict()}
        return enforce(announce(COMMAND, stopped, "secrets_unscanned", reason, detail))
    found = evaluate(state, SUBJECT, POLICY, ENTRYPOINT)
    decision = decide(found)
    data = {**state.model_dump(mode="json"), "decision": decision.model_dump(mode="json")}
    if decision.action != "proceed":
        code = refusal_code(decision, "secrets_refused")
        return enforce(announce(COMMAND, decision, code, reasons(found), data))
    message = "no finding in the repository's history"
    return enforce(announce(COMMAND, decision, "secrets_verified", message, data))


if __name__ == "__main__":
    raise SystemExit(main())
