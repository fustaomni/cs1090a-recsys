"""GREEN is a verdict from the runner's JUnit report, with its scope declared (A.32).

A PASS IS A VERDICT, NOT THE DEFAULT. GREEN needs exit 0, a report this run wrote, at least one
test that actually ran, nothing failed or errored, and every required proof passed. A run in
which nothing was evaluated blocks rather than passing vacuously: a skip attests nothing, so
evaluated counts passed, failed and errored cases, never skipped or merely discovered ones.

THE SCOPE IS PART OF THE VERDICT. A full run is the whole suite. A selected run names its
targets and must say why that selection suffices; without the explanation it is not green.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from junit_report import ReportError, filesystem_now, load, node_of, outcome_of

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / ".artifacts" / "runs" / "green"
USAGE = "usage: green_verify.py [--selected <why> <target>...] [--require <node>]..."

Scope = Literal["full", "selected"]
ReasonCode = Literal[
    "GREEN",
    "REFUSED_SELECTION_UNEXPLAINED",
    "REFUSED_NO_REPORT",
    "REFUSED_STALE_REPORT",
    "REFUSED_MALFORMED_REPORT",
    "REFUSED_NOTHING_EVALUATED",
    "REFUSED_FAILURES",
    "REFUSED_EXIT_CODE",
    "REFUSED_REQUIRED_NOT_PASSED",
]


class GreenVerdict(BaseModel):
    """green-verdict/v1: whether a run passed, over what scope, and how much it evaluated."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    contract: Literal["green-verdict/v1"] = "green-verdict/v1"
    scope: Scope
    explanation: str | None
    exit_code: int
    report: str
    evaluated: int
    skipped: int
    reason_code: ReasonCode
    detail: str

    @property
    def is_green(self) -> bool:
        return self.reason_code == "GREEN"


def judge(
    exit_code: int,
    report: Path,
    started: float,
    scope: Scope,
    explanation: str | None,
    required: tuple[str, ...],
) -> GreenVerdict:
    """The verdict for one run over its declared scope."""

    def verdict(
        code: ReasonCode, detail: str, evaluated: int = 0, skipped: int = 0
    ) -> GreenVerdict:
        return GreenVerdict(
            scope=scope,
            explanation=explanation,
            exit_code=exit_code,
            report=str(report),
            evaluated=evaluated,
            skipped=skipped,
            reason_code=code,
            detail=detail,
        )

    if scope == "selected" and not (explanation or "").strip():
        return verdict("REFUSED_SELECTION_UNEXPLAINED", "a selected run must say why it suffices")
    try:
        cases = load(report, started)
    except ReportError as problem:
        return verdict(problem.code, problem.detail)
    outcomes = {node_of(case): outcome_of(case) for case in cases}
    skipped = sum(1 for outcome in outcomes.values() if outcome == "skipped")
    evaluated = len(outcomes) - skipped
    if evaluated == 0:
        return verdict("REFUSED_NOTHING_EVALUATED", "no test ran", evaluated, skipped)
    failing = sorted(node for node, outcome in outcomes.items() if outcome in ("failed", "error"))
    if failing:
        return verdict("REFUSED_FAILURES", "failed: " + ", ".join(failing), evaluated, skipped)
    if exit_code != 0:
        detail = f"exit {exit_code}; green is exit 0"
        return verdict("REFUSED_EXIT_CODE", detail, evaluated, skipped)
    missing = [node for node in required if outcomes.get(node) != "passed"]
    if missing:
        detail = "required but not passed: " + ", ".join(missing)
        return verdict("REFUSED_REQUIRED_NOT_PASSED", detail, evaluated, skipped)
    return verdict("GREEN", f"{evaluated} passed over a {scope} run", evaluated, skipped)


def _arguments(argv: list[str]) -> tuple[Scope, str | None, tuple[str, ...], tuple[str, ...]]:
    """Scope, explanation, required nodes and targets from the command line."""
    scope: Scope = "full"
    explanation: str | None = None
    required: list[str] = []
    targets: list[str] = []
    rest = list(argv)
    while rest:
        head = rest.pop(0)
        if head == "--selected" and rest:
            scope = "selected"
            explanation = rest.pop(0)
        elif head == "--require" and rest:
            required.append(rest.pop(0))
        elif head.startswith("--"):
            raise SystemExit(USAGE)
        else:
            targets.append(head)
    if scope == "full" and targets:
        raise SystemExit("a full run takes no targets; name a selection with --selected <why>")
    if scope == "selected" and not targets:
        raise SystemExit("a selected run names its targets")
    return scope, explanation, tuple(required), tuple(targets)


def pytest_argv(report: Path, targets: tuple[str, ...]) -> list[str]:
    """A full run keeps addopts' level filter; a named selection lifts it with -m "" (A.141)."""
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    argv += ["--junitxml", str(report)]
    return [*argv, *targets, "-m", ""] if targets else argv


def main() -> int:
    scope, explanation, required, targets = _arguments(sys.argv[1:])
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = REPORTS / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{scope}.xml"
    started = filesystem_now(REPORTS)
    ran = subprocess.run(pytest_argv(report, targets), cwd=ROOT, check=False)
    result = judge(ran.returncode, report, started, scope, explanation, required)
    print(result.model_dump_json(indent=2))
    return 0 if result.is_green else 2


if __name__ == "__main__":
    raise SystemExit(main())
