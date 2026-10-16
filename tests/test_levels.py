"""Every test takes its level from its directory, and an unclassified test is refused (A.39)."""

from __future__ import annotations

import pytest

from levels import classify

DECLARED = {"tests": "unit", "tests/acceptance": "acceptance"}


def test_an_unclassified_test_is_refused() -> None:
    assert classify("tests/test_a.py::test_x", [], DECLARED) == "unit"
    deeper = "tests/acceptance/test_b.py::test_y"
    assert classify(deeper, ["acceptance"], DECLARED) == "acceptance"
    with pytest.raises(ValueError, match="declares no level"):
        classify("scratch/test_c.py::test_z", [], DECLARED)
    with pytest.raises(ValueError, match="but tests is unit"):
        classify("tests/test_d.py::test_w", ["acceptance"], DECLARED)
