"""A RED is a verdict from the runner's JUnit report, never from log text (A.31).

DECIDED FROM THE REPORT, NOT THE EXIT CODE ALONE. A missing module is a collection error with
exit 2, and --continue-on-collection-errors turns it into exit 1 with nothing run, so neither
code decides alone. The verdict reads the JUnit report this run wrote (pytest's own format:
<failure> for a test that failed, <error message="collection failure"> for one that never
loaded, <skipped> for a skip) and returns a closed reason.

ONLY A BEHAVIOURAL RED SATISFIES RED_VERIFIED: exit 1, the named node failing, nothing else
failing and nothing failing to collect. Collection errors that are all a missing module are an
import red, recorded but never sufficient, since they show the code is absent, not wrong.

The report is read by junit_report, the one reader the GREEN verdict shares.
"""

from __future__ import annotations

import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from junit_report import ReportError, load, node_of, outcome_of

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / ".artifacts" / "runs" / "red"
IMPORT_ERRORS = ("ModuleNotFoundError", "ImportError")

ReasonCode = Literal[
    "RED_BEHAVIOURAL",
    "RED_IMPORT",
    "REFUSED_EXIT_CODE",
    "REFUSED_NO_REPORT",
    "REFUSED_STALE_REPORT",
    "REFUSED_MALFORMED_REPORT",
    "REFUSED_COLLECTION_ERROR",
    "REFUSED_NODE_MISSING",
    "REFUSED_NODE_NOT_FAILED",
    "REFUSED_UNRELATED_FAILURE",
]
RedKind = Literal["behavioural", "import"]


class RedVerdict(BaseModel):
    """red-verdict/v1: whether a run showed the named proof failing for its behaviour."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    contract: Literal["red-verdict/v1"] = "red-verdict/v1"
    node: str
    exit_code: int
    report: str
    reason_code: ReasonCode
    red_kind: RedKind | None = None
    detail: str

    @property
    def satisfies_red_verified(self) -> bool:
        return self.reason_code == "RED_BEHAVIOURAL"


def _text(element: ET.Element) -> str:
    return f"{element.get('message', '')} {element.text or ''}"


def judge(exit_code: int, report: Path, node: str, started: float) -> RedVerdict:
    """The verdict for one run: exit code, its report, the named node, and when it started."""

    def verdict(code: ReasonCode, detail: str, kind: RedKind | None = None) -> RedVerdict:
        return RedVerdict(
            node=node,
            exit_code=exit_code,
            report=str(report),
            reason_code=code,
            red_kind=kind,
            detail=detail,
        )

    try:
        cases = load(report, started)
    except ReportError as problem:
        return verdict(problem.code, problem.detail)
    collection = [
        error for case in cases if not case.get("classname") for error in case.findall("error")
    ]
    if collection:
        if exit_code == 2 and all(
            any(name in _text(error) for name in IMPORT_ERRORS) for error in collection
        ):
            return verdict("RED_IMPORT", "every collection error is a missing module", "import")
        return verdict("REFUSED_COLLECTION_ERROR", f"{len(collection)} collection error(s)")
    if exit_code != 1:
        return verdict("REFUSED_EXIT_CODE", f"exit {exit_code}; a red is exit 1")
    target = [case for case in cases if node_of(case) == node]
    if not target:
        return verdict("REFUSED_NODE_MISSING", f"{node} was not collected")
    failure = target[0].find("failure")
    if failure is None:
        return verdict("REFUSED_NODE_NOT_FAILED", f"{node} did not fail on its behaviour")
    others = [
        node_of(case)
        for case in cases
        if node_of(case) != node and outcome_of(case) in ("failed", "error")
    ]
    if others:
        return verdict("REFUSED_UNRELATED_FAILURE", "also failed: " + ", ".join(others))
    return verdict("RED_BEHAVIOURAL", failure.get("message", ""), "behavioural")


def main() -> int:
    match sys.argv[1:]:
        case [node] if "::" in node:
            REPORTS.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            report = REPORTS / f"{stamp}-{node.split('::')[-1]}.xml"
            started = time.time()
            argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
            argv += ["--junitxml", str(report), node.split("::")[0]]
            ran = subprocess.run(argv, cwd=ROOT, check=False)
            result = judge(ran.returncode, report, node, started)
            print(result.model_dump_json(indent=2))
            return 0 if result.satisfies_red_verified else 2
        case other:
            raise SystemExit(f"usage: red_verify.py <tests/file.py::test_name>  (got {other})")


if __name__ == "__main__":
    raise SystemExit(main())
