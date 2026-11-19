"""Every toolchain operation is a task, recorded like every other operation (A.26).

The founding ran mise lock and mise install by hand, and neither left a run record. tools:lock
writes mise.lock for each development platform (A.347), and tools:install installs exactly
what it records. Each is a task, so it runs through the gateway and is recorded, and each is a
registered capability.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("linux-x64", "macos-arm64")
TOOLCHAIN = {
    "tools:lock": f"mise lock --platform {','.join(PLATFORMS)}",
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
    for task, command in nonempty(TOOLCHAIN.items()):
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
    assert platforms == set(PLATFORMS), platforms


def test_a_tool_arrives_only_through_tools_install() -> None:
    """A.103: mise's auto-install is off, in mise.toml and the founding data's pins alike."""
    settings = _load("mise.toml")["settings"]
    assert isinstance(settings, dict) and settings.get("auto_install") is False, settings
    data = ROOT / "policies" / "founding" / "data.json"
    pinned = json.loads(data.read_text(encoding="utf-8"))["founding"]["pins"]["settings"]
    assert pinned.get("auto_install") is False, pinned
