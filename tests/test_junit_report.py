"""A report's freshness is judged in its own file system's clock (A.88).

A file's mtime comes from the clock of the file system that holds it, which on network storage is
the server's. The start of a run is taken from a marker written in the same directory, so a report
written after it can never appear older than the run that wrote it.
"""

from __future__ import annotations

from pathlib import Path

import junit_report


def test_freshness_is_judged_in_the_report_directorys_own_clock(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    started = junit_report.filesystem_now(reports)
    report = reports / "report.xml"
    report.write_text("<testsuites />", encoding="utf-8")
    assert report.stat().st_mtime >= started
    assert list(reports.iterdir()) == [report]
