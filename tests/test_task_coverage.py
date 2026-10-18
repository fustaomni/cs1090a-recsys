"""Every toolchain operation is a task, recorded like every other operation (A.26).

The founding ran mise lock and mise install by hand, and neither left a run record. tools:lock
writes mise.lock for the one platform this repository locks, and tools:install installs exactly
what it records. Each is a task, so it runs through the gateway and is recorded, and each is a
registered capability.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = "linux-x64"
TOOLCHAIN = {
    "tools:lock": f"mise lock --platform {PLATFORM}",
    "tools:install": "mise install --locked",
}


def _load(*parts: str) -> dict[str, object]:
    return tomllib.loads(ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def test_every_toolchain_operation_is_a_task() -> None:
    tasks = _load("mise.toml")["tasks"]
    assert isinstance(tasks, dict), tasks
    listed = _load("contracts", "capabilities.toml")["capabilities"]
    assert isinstance(listed, list), listed
    registered = {entry["task"] for entry in listed if isinstance(entry, dict)}
    for task, command in TOOLCHAIN.items():
        body = tasks.get(task)
        assert isinstance(body, dict) and body.get("run") == command, (task, body)
        assert task in registered, f"{task} is not a registered capability"
    locked = _load("mise.lock")["tools"]
    assert isinstance(locked, dict), locked
    platforms = {
        key.removeprefix("platforms.")
        for entries in locked.values()
        for key in entries[0]
        if key.startswith("platforms.")
    }
    assert platforms == {PLATFORM}, platforms
