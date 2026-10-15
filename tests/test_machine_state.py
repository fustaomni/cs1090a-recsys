# tests/test_machine_state.py
"""This machine's mise state and new files are owner-only, whatever the platform's umask (A.8).

FAS OnDemand's ~/.bashrc sets umask 0002, the user-private-group convention, but here the
primary group is shared (ondemand-users-*), so 0002 made mise's trust records, its config
(where paranoid = true lives) and its installs writable by every member of that group. Those
are exactly what nobody else may be able to replace. The directories must exist, so the check
cannot pass on nothing.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


def _mise_dirs() -> list[Path]:
    home = Path.home()
    return [
        Path(os.environ.get("MISE_STATE_DIR", home / ".local" / "state" / "mise")),
        Path(os.environ.get("MISE_CONFIG_DIR", home / ".config" / "mise")),
    ]


def _writable_by_others(root: Path) -> list[str]:
    found = []
    for path in [root, *root.rglob("*")]:
        if not path.is_symlink() and path.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            found.append(str(path))
    return sorted(found)


def test_mise_state_is_owner_only() -> None:
    dirs = _mise_dirs()
    missing = [str(d) for d in dirs if not d.is_dir()]
    assert not missing, "not found, so nothing would be checked: " + ", ".join(missing)
    loose = [path for d in dirs for path in _writable_by_others(d)]
    assert not loose, f"{len(loose)} group- or world-writable: " + "; ".join(loose[:8])


def test_the_umask_never_grants_group_or_world_write() -> None:
    current = os.umask(0o077)
    os.umask(current)
    assert current & 0o022 == 0o022, f"umask {current:04o} lets the group or the world write"
