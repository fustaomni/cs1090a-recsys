# tests/test_lock.py
"""A lock that no longer agrees with its project is refused (A.146).

This repository's own lock is proven at tests/integration/test_repository_lock.py, after a sync.

cs1090a-volatility was born with a lock whose root still named the template, and no proof saw
it: the identity policy scans for the declared value outside its slots, never a slot holding
another. uv lock --check asserts the lock would stay unchanged by a resolution, so it fails on
exactly that, offline, from the cache the project's own sync filled.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT = (
    '[project]\nname = "{name}"\nversion = "0.1.0"\nrequires-python = ">=3.12"\ndependencies = []\n'
)


def _uv(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """uv in root's own environment: no inherited virtualenv."""
    environment = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    return subprocess.run(
        ["uv", *args], cwd=root, env=environment, capture_output=True, text=True, check=False
    )


def _lock_checked(root: Path) -> subprocess.CompletedProcess[str]:
    return _uv(root, "lock", "--check", "--offline")


def test_a_lock_naming_another_project_is_refused(tmp_path: Path) -> None:
    """The paired negative control: the check bites on a project renamed past its lock.

    ZERO DEPENDENCIES, as cscie103's D.263 proves its relock: re-resolving such a project needs
    no registry, so offline the check fails for staleness alone, never for a cold cache.
    """
    project = tmp_path / "pyproject.toml"
    project.write_text(PROJECT.format(name="zqx-locked-project"), encoding="utf-8")
    locked = _uv(tmp_path, "lock", "--offline")
    assert locked.returncode == 0, locked.stderr
    current = _lock_checked(tmp_path)
    assert current.returncode == 0, current.stderr
    project.write_text(PROJECT.format(name="zqx-renamed-project"), encoding="utf-8")
    stale = _lock_checked(tmp_path)
    assert stale.returncode != 0, stale.stdout
    # UV'S OWN REASON: the lock, not the resolver, is what the check refused.
    assert "needs to be updated" in stale.stderr, stale.stderr
