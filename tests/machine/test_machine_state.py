# tests/machine/test_machine_state.py
"""This machine's mise state and new files are owner-only, whatever the platform's umask (A.8).

FAS OnDemand's ~/.bashrc sets umask 0002, the user-private-group convention, but here the
primary group is shared (ondemand-users-*), so 0002 made mise's trust records, its config
(where paranoid = true lives) and its installs writable by every member of that group. Those
are exactly what nobody else may be able to replace. The directories must exist, so the check
cannot pass on nothing.

A CLAIM ABOUT THIS MACHINE (A.104): it lives in tests/machine, the machine lane, which this
machine's hooks and gates run and CI's runner, which is not this machine, never does.
"""

from __future__ import annotations

import os
import stat
import subprocess
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


def test_a_new_login_shell_never_grants_group_or_world_write() -> None:
    """The umask a new session starts with: what every terminal and hook from now on inherits.

    Measured in a fresh login shell, not in this process: a umask is inherited from whichever
    terminal launched the tests, and one opened before the fix keeps the platform's 0002.
    """
    shell = ["env", "-i", f"HOME={Path.home()}", "TERM=dumb", "bash", "-l", "-c", "umask"]
    done = subprocess.run(shell, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    mask = int(done.stdout.strip().splitlines()[-1], 8)
    assert mask & 0o022 == 0o022, f"a new login shell's umask {mask:04o} lets others write"
