"""A claim about this machine runs in this machine's gates, never on CI's runner (A.104).

A.8's proofs judge this FAS OnDemand machine's mise state and umask. CI ran them on GitHub's
runner, where they prove nothing about this machine. They live in tests/machine, a lane declared
by directory (A.39): excluded from the hermetic lane, run by the test (machine) gate in the hooks
and the snapshot before every publication, and omitted from CI's gate by the gate's declaration.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from check_all import GATES

ROOT = Path(__file__).resolve().parent.parent


def _toml(*parts: str) -> dict[str, object]:
    return tomllib.loads(ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def test_a_machine_claim_runs_here_and_never_on_ci() -> None:
    levels = _toml("contracts", "test-levels.toml")["directories"]
    assert isinstance(levels, dict) and levels.get("tests/machine") == "machine", levels
    assert (ROOT / "tests" / "machine" / "test_machine_state.py").is_file(), "not moved"
    assert not (ROOT / "tests" / "test_machine_state.py").exists(), "still in the unit lane"

    tool = _toml("pyproject.toml")["tool"]
    assert isinstance(tool, dict), tool
    options = tool["pytest"]["ini_options"]
    assert any(str(m).startswith("machine:") for m in options["markers"]), options["markers"]
    addopts = options["addopts"]
    marked = addopts[addopts.index("-m") + 1]
    assert marked == "not integration and not machine", addopts

    lanes = [spec for spec in GATES if spec.name == "test (machine)"]
    assert len(lanes) == 1, [spec.name for spec in GATES]
    lane = lanes[0]
    assert lane.command[-2:] == ("-m", "machine"), lane.command
    assert lane.runs_in_hooks, "the hooks and the pre-publication snapshot must run it here"
    assert lane.runs_in_ci is False, "CI's runner is not this machine"

    tasks = _toml("mise.toml")["tasks"]
    assert isinstance(tasks, dict), tasks
    assert tasks["check:ci"]["run"] == "uv run --no-sync python scripts/check_all.py --ci"
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "run: mise run check:ci" in workflow, "CI must run the gate without the machine lane"
