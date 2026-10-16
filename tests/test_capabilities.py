"""Every task is a registered capability, checked against mise.toml and its own code (A.44)."""

from __future__ import annotations

from pathlib import Path

from capabilities import ROOT, Capabilities, Capability, findings, load
from run_task import declared_tasks, read_only_tasks


def test_every_task_is_a_registered_capability() -> None:
    assert findings(load(ROOT), declared_tasks(), read_only_tasks(ROOT), ROOT) == []


def test_a_mislabelled_or_missing_capability_is_refused(tmp_path: Path) -> None:
    builds = "from command_outcome import CommandOutcome\n"
    (tmp_path / "envelope.py").write_text(builds, encoding="utf-8")
    (tmp_path / "plain.py").write_text("print('done')\n", encoding="utf-8")
    register = Capabilities(
        capabilities=(
            Capability(task="a", version="1.0.0", implementation="envelope.py", emits="text"),
            Capability(
                task="b", version="1.0.0", implementation="plain.py", emits="red-verdict/v2"
            ),
            Capability(task="c", version="1.0.0", implementation="gone.py", emits="text"),
            Capability(
                task="d", version="1.0.0", implementation="envelope.py", emits="command-outcome/v1"
            ),
        )
    )
    assert findings(register, {"a", "b", "c", "d", "e"}, {"f"}, tmp_path) == [
        "e: a task with no capability",
        "a: envelope.py does not emit text",
        "b: plain.py does not emit red-verdict/v2",
        "c: gone.py is not a file",
        "f: read-only but not a declared task",
    ]
