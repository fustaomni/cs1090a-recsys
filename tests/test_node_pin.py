# tests/test_node_pin.py
"""The site's node is a locked project tool (A.361).

WHY. Twelve site tasks run `mise exec node@24`, but mise.toml's [tools] named no node, so
mise.lock recorded none: tools:install (mise install --locked) installed seven tools and
never the site's node, which mise then fetched unlocked on first use. Locked mode refuses a
tool the lock lacks and, since mise 2026.11, a platform entry without a checksum.

WHAT IS PROVEN. [tools] pins node at the major the tasks run; every `mise exec node@N` names
that major; and mise.lock records node for every development platform with a sha256 checksum.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("linux-x64", "macos-arm64")
NODE_EXEC = re.compile(r"mise exec node@(\d+)")


def _toml(name: str) -> dict[str, Any]:
    return tomllib.loads((ROOT / name).read_text(encoding="utf-8"))


def _pinned() -> object:
    tools = _toml("mise.toml").get("tools", {})
    return tools.get("node") if isinstance(tools, dict) else None


def _platforms(entry: dict[str, Any]) -> dict[str, Any]:
    """mise.lock's per-platform tables, nested or written as dotted "platforms.<p>" keys."""
    nested = entry.get("platforms", {})
    flat = {k.removeprefix("platforms."): v for k, v in entry.items() if k.startswith("platforms.")}
    return {**(nested if isinstance(nested, dict) else {}), **flat}


def test_node_is_a_pinned_project_tool() -> None:
    assert re.fullmatch(r"24\.\d+\.\d+", str(_pinned())), _pinned()


def test_every_site_task_runs_the_pinned_node_major() -> None:
    majors = NODE_EXEC.findall((ROOT / "mise.toml").read_text(encoding="utf-8"))
    for major in nonempty(majors):
        assert major == str(_pinned()).split(".")[0], (major, _pinned())


def test_the_lock_records_node_for_every_development_platform() -> None:
    tools = _toml("mise.lock").get("tools", {})
    found = tools.get("node", []) if isinstance(tools, dict) else []
    entries = [found] if isinstance(found, dict) else list(found)
    for entry in nonempty(entries):
        assert str(entry.get("version", "")).startswith("24."), entry
        platforms = _platforms(entry)
        for platform in nonempty(PLATFORMS):
            checksum = str(platforms.get(platform, {}).get("checksum", ""))
            assert checksum.startswith("sha256:"), (platform, platforms)
