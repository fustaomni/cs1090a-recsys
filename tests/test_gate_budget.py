# tests/test_gate_budget.py
"""The test gate's deadline is computed from its measured duration, never typed (A.278).

A typed 900 s killed a suite that passes in 1108 s on a slower node. The deadline is the slowest
passing run measured times the runaway-backstop multiplier, so slow is never mistaken for hung.
"""

from __future__ import annotations

import check_all

SLOWEST_PASSING_SECONDS = 1108.0  # 2026-11-10, FAS node cr-2, every test passing
BACKSTOP = 3.0


def test_the_test_gate_deadline_is_computed_from_its_measurement() -> None:
    measured = float(getattr(check_all, "TEST_MEASURED_SECONDS", 0.0))
    headroom = float(getattr(check_all, "TEST_HEADROOM", 0.0))
    gates = [gate for gate in check_all.GATES if gate.name == "test"]
    assert len(gates) == 1, [gate.name for gate in check_all.GATES]
    assert gates[0].timeout_seconds == measured * headroom, (gates[0], measured, headroom)
    assert measured >= SLOWEST_PASSING_SECONDS and headroom >= BACKSTOP, (measured, headroom)
