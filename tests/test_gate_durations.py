# tests/test_gate_durations.py
"""Every pytest run reports its slowest phases, so a gate's time is measured (A.263)."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_every_run_reports_its_slowest_phases() -> None:
    """The slowest twenty setup, call and teardown phases over one second are printed."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = config["tool"]["pytest"]["ini_options"]["addopts"]
    assert "--durations=20" in addopts, addopts
    assert "--durations-min=1.0" in addopts, addopts
