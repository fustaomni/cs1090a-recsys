"""Every expectation kind the plan uses has its runtime record type and producer (A.65)."""

from __future__ import annotations

from pathlib import Path

from capabilities import Capabilities, Capability
from capabilities import load as load_capabilities
from expectations import ROOT, Expectation, Expectations, findings, load, used_kinds


def test_every_expectation_the_plan_uses_has_a_record_and_producer() -> None:
    assert findings(load(ROOT), used_kinds(ROOT), load_capabilities(ROOT), ROOT) == []


def test_an_expectation_without_a_record_type_is_refused(tmp_path: Path) -> None:
    (tmp_path / "carrier.py").write_text('CARRIES = "source-lines/v1"\n', encoding="utf-8")
    green = Capability(
        task="green", version="1.0.0", implementation="carrier.py", emits="green-verdict/v1"
    )
    read = Capability(
        task="read", version="1.0.0", implementation="carrier.py", emits="command-outcome/v1"
    )
    register = Expectations(
        expectations=(
            Expectation(kind="proof", record="green-verdict/v1", producer="green"),
            Expectation(kind="path", record="source-lines/v1", producer="read"),
            Expectation(kind="task", record="capabilities-listing/v1", producer="absent"),
            Expectation(kind="release", record="release-record/v1", producer="green"),
        )
    )
    used = {"proof", "path", "task", "release", "pr"}
    assert findings(register, used, Capabilities(capabilities=(green, read)), tmp_path) == [
        "pr: used by the plan with no record type",
        "task: absent is not a registered capability",
        "release: green does not produce release-record/v1",
    ]
