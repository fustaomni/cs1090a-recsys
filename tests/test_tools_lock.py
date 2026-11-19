# tests/test_tools_lock.py
"""Every locked tool has an entry for each development platform (A.347).

The MacBook Pro develops beside FAS OnDemand, and mise install --locked installs only what
mise.lock records for the running platform. A tool locked for linux-x64 alone cannot be
installed on macos-arm64 without resolving it from the network.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("linux-x64", "macos-arm64")


def test_every_locked_tool_has_an_entry_for_each_development_platform() -> None:
    lock: dict[str, object] = tomllib.loads((ROOT / "mise.lock").read_text(encoding="utf-8"))
    tools = lock["tools"]
    assert isinstance(tools, dict) and tools, lock.keys()
    missing: list[str] = []
    for name, entries in nonempty(tools.items()):
        assert isinstance(entries, list) and entries, name
        for entry in nonempty(entries):
            assert isinstance(entry, dict), name
            missing += [f"{name}: {key}" for key in PLATFORMS if f"platforms.{key}" not in entry]
    assert not missing, missing
