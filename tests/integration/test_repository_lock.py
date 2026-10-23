# tests/integration/test_repository_lock.py
"""This repository's lock agrees with its project (A.146).

INTEGRATION, NOT HERMETIC: even a current lock is checked by re-resolving it, and offline that
needs the registry metadata only a sync leaves in the project's cache. check and CI run this
tier after their sync; the snapshot gate, which never syncs, proves the lock its own way (R5).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.integration
def test_this_repositorys_lock_matches_its_project() -> None:
    environment = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    done = subprocess.run(
        ["uv", "lock", "--check", "--offline"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
