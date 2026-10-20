# tests/test_pr_logs_task.py
"""pr:logs runs the ported reader, read-only, as cscie103 declares it (A.142).

scripts/pr_logs.py and its proof were ported with no task to run them, so the run gateway
refused pr:logs as undeclared and a failed CI run could not be read through it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _toml(name: str) -> dict[str, object]:
    return tomllib.loads((ROOT / name).read_text(encoding="utf-8"))


def test_pr_logs_runs_the_ported_reader() -> None:
    tasks = _toml("mise.toml")["tasks"]
    assert isinstance(tasks, dict), tasks
    assert tasks["pr:logs"]["run"] == "uv run --no-sync python scripts/pr_logs.py"


def test_pr_logs_is_read_only_and_a_capability() -> None:
    effects = _toml("contracts/task-effects.toml")["read_only"]
    assert isinstance(effects, list), effects
    assert "pr:logs" in effects, effects
    listed = _toml("contracts/capabilities.toml")["capabilities"]
    assert isinstance(listed, list), listed
    found = [entry for entry in listed if entry["task"] == "pr:logs"]
    expected = {
        "task": "pr:logs",
        "version": "1.0.0",
        "implementation": "scripts/pr_logs.py",
        "emits": "command-outcome/v1",
    }
    assert found == [expected], found
