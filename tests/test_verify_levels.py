# tests/test_verify_levels.py
"""A named proof runs whatever its level; a full GREEN keeps the level filter (A.141).

pyproject's addopts deselects integration and machine tests from a bare pytest run. The
verifiers ran named proofs through that same filter, so an integration proof could be shown
neither RED nor GREEN. pytest takes the last -m given, and an empty one selects every test.
"""

from __future__ import annotations

from pathlib import Path

import green_verify
import red_verify

REPORT = Path("report.xml")


def test_red_runs_named_proofs_at_any_level() -> None:
    argv = red_verify.pytest_argv(REPORT, ["tests/integration/test_x.py"])
    assert argv[-2:] == ["-m", ""], argv


def test_a_selected_green_runs_its_targets_at_any_level() -> None:
    argv = green_verify.pytest_argv(REPORT, ("tests/integration/test_x.py",))
    assert argv[-2:] == ["-m", ""], argv


def test_a_full_green_keeps_the_level_filter() -> None:
    argv = green_verify.pytest_argv(REPORT, ())
    assert "-m" not in argv[3:], argv
