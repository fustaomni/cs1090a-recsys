# tests/test_types_budget.py
"""Each type gate's deadline is its measured runtime times the headroom (A.333).

As A.278 and A.340 compute the test tiers' deadlines, the type gates' deadline is the slowest
recorded run of the type checks times the runaway-backstop headroom, never a typed number.
"""

from __future__ import annotations

import check_all


def test_each_type_gate_deadline_is_its_measured_runtime_times_the_headroom() -> None:
    measured = float(getattr(check_all, "TYPES_MEASURED_SECONDS", 0.0))
    headroom = float(getattr(check_all, "TEST_HEADROOM", 0.0))
    assert measured > 0, "check_all.py records no measured type-check runtime"
    deadlines = {
        spec.name: spec.timeout_seconds for spec in check_all.GATES if spec.name.startswith("types")
    }
    expected = {"types (darwin)": measured * headroom, "types (linux)": measured * headroom}
    assert deadlines == expected, deadlines
