"""GREEN is a verdict from the runner's JUnit report, with its scope declared (A.32).

GREEN needs exit 0, a report this run wrote, something actually evaluated, nothing failed and
every required proof passed; a selected run must say why its selection suffices.
"""

from __future__ import annotations

import time
from pathlib import Path

import green_verify

NODE = "tests/test_widget.py::test_widget_takes_base"
PASSED = '<testcase classname="tests.test_widget" name="test_widget_takes_base" />'
PASSED_OTHER = '<testcase classname="tests.test_other" name="test_other_holds" />'
FAILED_OTHER = (
    '<testcase classname="tests.test_other" name="test_other_breaks">'
    '<failure message="AssertionError">trace</failure></testcase>'
)
SKIPPED = (
    '<testcase classname="tests.test_widget" name="test_widget_takes_base">'
    '<skipped type="pytest.skip" message="skipped">reason</skipped></testcase>'
)


def _report(tmp_path: Path, cases: str) -> Path:
    path = tmp_path / "report.xml"
    head = '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">'
    path.write_text(head + cases + "</testsuite></testsuites>", encoding="utf-8")
    return path


def _judge(
    exit_code: int, report: Path, scope: green_verify.Scope = "full", why: str | None = None
) -> str:
    started = time.time() - 60
    return green_verify.judge(exit_code, report, started, scope, why, (NODE,)).reason_code


def test_green_needs_exit_zero_and_a_report_from_this_run(tmp_path: Path) -> None:
    report = _report(tmp_path, PASSED + PASSED_OTHER)
    assert _judge(0, report) == "GREEN"
    assert _judge(1, report) == "REFUSED_EXIT_CODE"
    assert _judge(0, tmp_path / "absent.xml") == "REFUSED_NO_REPORT"
    assert _judge(1, _report(tmp_path, PASSED + FAILED_OTHER)) == "REFUSED_FAILURES"


def test_a_selected_run_without_a_selection_explanation_is_not_green(tmp_path: Path) -> None:
    report = _report(tmp_path, PASSED)
    assert _judge(0, report, "selected") == "REFUSED_SELECTION_UNEXPLAINED"
    assert _judge(0, report, "selected", "   ") == "REFUSED_SELECTION_UNEXPLAINED"
    explained = green_verify.judge(0, report, 0.0, "selected", "widget only", (NODE,))
    assert (explained.reason_code, explained.scope) == ("GREEN", "selected")


def test_zero_evaluated_checks_blocks(tmp_path: Path) -> None:
    assert _judge(5, _report(tmp_path, "")) == "REFUSED_NOTHING_EVALUATED"
    assert _judge(0, _report(tmp_path, SKIPPED)) == "REFUSED_NOTHING_EVALUATED"


def test_a_required_proof_that_did_not_pass_is_not_green(tmp_path: Path) -> None:
    assert _judge(0, _report(tmp_path, PASSED_OTHER)) == "REFUSED_REQUIRED_NOT_PASSED"
