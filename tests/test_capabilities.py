"""Every task is a registered capability, checked against mise.toml and its own code (A.44)."""

from __future__ import annotations

import tomllib
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


NEWLINE = chr(10)


def _raw_args_tasks() -> dict[str, dict[str, object]]:
    """mise.toml's tasks that forward their arguments unparsed."""
    document = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
    tasks: dict[str, dict[str, object]] = document["tasks"]
    return {name: body for name, body in tasks.items() if body.get("raw_args") is True}


def test_every_raw_args_task_declares_its_arguments_as_its_script_states_them() -> None:
    # A.320: each task forwarding its arguments unparsed declares them as its script states them.
    raw = _raw_args_tasks()
    assert raw, "mise.toml declares no raw_args task"
    undeclared = sorted(name for name, body in raw.items() if "usage" not in body)
    assert undeclared == [], undeclared
    assert findings(load(ROOT), declared_tasks(), read_only_tasks(ROOT), ROOT) == []


def test_a_raw_args_task_without_its_declared_arguments_is_refused(tmp_path: Path) -> None:
    # A.320: no usage spec, or an argument its script never states, is a finding by name.
    step = "usage = 'arg " + '"<step>"' + "'"
    lines = ["[tasks.bare]", "raw_args = true", 'run = "true"', "[tasks.drift]"]
    lines += ["raw_args = true", step, 'run = "true"']
    (tmp_path / "mise.toml").write_text(NEWLINE.join(lines) + NEWLINE, encoding="utf-8")
    (tmp_path / "bare.py").write_text("print('done')" + NEWLINE, encoding="utf-8")
    (tmp_path / "drift.py").write_text("print('usage: drift <slug>')" + NEWLINE, encoding="utf-8")
    register = Capabilities(
        capabilities=(
            Capability(task="bare", version="1.0.0", implementation="bare.py", emits="text"),
            Capability(task="drift", version="1.0.0", implementation="drift.py", emits="text"),
        )
    )
    assert findings(register, {"bare", "drift"}, set(), tmp_path) == [
        "bare: raw_args with no usage spec",
        "drift: drift.py does not state <step>",
    ]
