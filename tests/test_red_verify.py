"""A RED is a verdict from the runner's JUnit report, never from log text (A.31).

Only exit 1 with the named node failing, nothing else failing and nothing failing to collect is
a behavioural red. Collection errors that are all a missing module are recorded as an import
red, which never satisfies RED_VERIFIED; anything else is refused with a closed reason.
"""

from __future__ import annotations

import time
from pathlib import Path

import red_verify

NODE = "tests/test_widget.py::test_widget_rejects_base"
FAILED = (
    '<testcase classname="tests.test_widget" name="test_widget_rejects_base">'
    '<failure message="TypeError: unexpected keyword base">trace</failure></testcase>'
)
PASSED_OTHER = '<testcase classname="tests.test_other" name="test_other_holds" />'
FAILED_OTHER = (
    '<testcase classname="tests.test_other" name="test_other_breaks">'
    '<failure message="AssertionError">trace</failure></testcase>'
)
IMPORT_ERROR = (
    '<testcase classname="" name="tests.test_widget">'
    '<error message="collection failure">ModuleNotFoundError: No module named widget</error>'
    "</testcase>"
)
SYNTAX_ERROR = (
    '<testcase classname="" name="tests.test_other">'
    '<error message="collection failure">SyntaxError: invalid syntax</error></testcase>'
)
SKIPPED = (
    '<testcase classname="tests.test_widget" name="test_widget_rejects_base">'
    '<skipped type="pytest.skip" message="skipped">reason</skipped></testcase>'
)


def _report(tmp_path: Path, cases: str) -> Path:
    path = tmp_path / "report.xml"
    head = '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">'
    path.write_text(head + cases + "</testsuite></testsuites>", encoding="utf-8")
    return path


def test_a_red_needs_exit_code_one_and_a_report_from_this_run(tmp_path: Path) -> None:
    started = time.time() - 60
    report = _report(tmp_path, FAILED + PASSED_OTHER)
    assert red_verify.judge(1, report, NODE, started).reason_code == "RED_BEHAVIOURAL"
    assert red_verify.judge(2, report, NODE, started).reason_code == "REFUSED_EXIT_CODE"
    absent = tmp_path / "absent.xml"
    assert red_verify.judge(1, absent, NODE, started).reason_code == "REFUSED_NO_REPORT"
    later = time.time() + 3600
    assert red_verify.judge(1, report, NODE, later).reason_code == "REFUSED_STALE_REPORT"


def test_a_collection_error_or_an_unrelated_failure_is_refused(tmp_path: Path) -> None:
    collection = _report(tmp_path, FAILED + SYNTAX_ERROR)
    assert red_verify.judge(2, collection, NODE, 0.0).reason_code == "REFUSED_COLLECTION_ERROR"
    unrelated = _report(tmp_path, FAILED + FAILED_OTHER)
    assert red_verify.judge(1, unrelated, NODE, 0.0).reason_code == "REFUSED_UNRELATED_FAILURE"


def test_an_import_red_never_satisfies_red_verified(tmp_path: Path) -> None:
    verdict = red_verify.judge(2, _report(tmp_path, IMPORT_ERROR), NODE, 0.0)
    assert (verdict.red_kind, verdict.reason_code) == ("import", "RED_IMPORT")
    assert not verdict.satisfies_red_verified


def test_a_missing_named_proof_is_refused_not_skipped(tmp_path: Path) -> None:
    missing = _report(tmp_path, FAILED_OTHER)
    assert red_verify.judge(1, missing, NODE, 0.0).reason_code == "REFUSED_NODE_MISSING"
    skipped = _report(tmp_path, SKIPPED + FAILED_OTHER)
    assert red_verify.judge(1, skipped, NODE, 0.0).reason_code == "REFUSED_NODE_NOT_FAILED"


def test_a_malformed_report_is_refused_not_raised(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text("<testsuites><testsuite>", encoding="utf-8")
    verdict = red_verify.judge(1, report, NODE, 0.0)
    assert verdict.reason_code == "REFUSED_MALFORMED_REPORT"
