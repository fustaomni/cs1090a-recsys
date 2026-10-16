"""Read the JUnit report a pytest run wrote, for the RED and GREEN verdicts (A.31, A.32).

ONE READER FOR BOTH VERDICTS. A report that is missing, older than the run, not well-formed XML
or rootless is a ReportError with a closed code, never an exception a caller must guess at.
The report is parsed with defusedxml, which refuses entity expansion and external references,
so even a tampered report cannot turn the parse against a verifier. A test case's node id is
rebuilt from pytest's classname and name; a collection error is a case with no classname.
"""

from __future__ import annotations

import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from defusedxml import DefusedXmlException
from defusedxml import ElementTree as SafeET

ProblemCode = Literal["REFUSED_NO_REPORT", "REFUSED_STALE_REPORT", "REFUSED_MALFORMED_REPORT"]
Outcome = Literal["passed", "failed", "error", "skipped"]


class ReportError(Exception):
    """A report that cannot be judged, with the closed reason a verdict carries."""

    def __init__(self, code: ProblemCode, detail: str) -> None:
        super().__init__(detail)
        self.code: ProblemCode = code
        self.detail = detail


def filesystem_now(directory: Path) -> float:
    """The current time as the file system holding directory stamps it (A.88).

    A report's mtime comes from the clock of the file system that holds it, on network storage
    the server's, not this process's; time.time() drifts from it. A marker written here just
    before a run gives the run's start in that same clock, so freshness compares like with like.
    """
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory) as marker:
        marker.write(b"start")
        marker.flush()
        return os.fstat(marker.fileno()).st_mtime


def load(report: Path, started: float) -> list[ET.Element]:
    """The test cases of a report this run wrote, or a ReportError saying why not."""
    if not report.is_file() or report.stat().st_size == 0:
        raise ReportError("REFUSED_NO_REPORT", "no report was written by this run")
    if report.stat().st_mtime < started:
        raise ReportError("REFUSED_STALE_REPORT", "the report predates this run")
    try:
        root = SafeET.parse(report).getroot()
    except (SafeET.ParseError, DefusedXmlException) as error:
        detail = f"the report is not readable XML: {error}"
        raise ReportError("REFUSED_MALFORMED_REPORT", detail) from error
    if root is None:
        raise ReportError("REFUSED_MALFORMED_REPORT", "the report has no root element")
    return list(root.iter("testcase"))


def node_of(case: ET.Element) -> str:
    """The pytest node id of a module-level test case."""
    module = case.get("classname", "")
    return f"{module.replace('.', '/')}.py::{case.get('name', '')}"


def outcome_of(case: ET.Element) -> Outcome:
    """How a test case ended, as pytest's JUnit writer records it."""
    if case.find("failure") is not None:
        return "failed"
    if case.find("error") is not None:
        return "error"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"
