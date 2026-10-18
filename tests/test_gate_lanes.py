"""A lane that may be empty reports it had nothing to run; any other lane fails on it (A.90).

pytest exits 5 when it collects nothing, and the gate treated that as failure, so the full gate
could never pass while no integration test existed. Treating it as a pass would hide a unit lane
whose tests vanished, so emptiness is declared per lane and reported as a state of its own.
"""

from __future__ import annotations

import sys

from check_all import GateSpec, run_gate


def _lane(*, may_be_empty: bool) -> GateSpec:
    return GateSpec(
        name="probe",
        command=(sys.executable, "-c", "import sys; sys.exit(5)"),
        runs_in_hooks=True,
        timeout_seconds=30.0,
        may_be_empty=may_be_empty,
    )


def test_a_lane_that_may_be_empty_reports_nothing_to_run() -> None:
    empty = run_gate(_lane(may_be_empty=True))
    assert (empty.state, empty.passed) == ("nothing_to_run", False)
    refused = run_gate(_lane(may_be_empty=False))
    assert (refused.state, refused.passed) == ("executed_failed", False)
