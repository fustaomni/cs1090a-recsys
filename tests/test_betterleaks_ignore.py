# tests/test_betterleaks_ignore.py
"""A reviewed finding stays suppressed in every commit of its line (A.341)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEWED = "scripts/tools_verify.py:generic-api-key:35"


def test_the_reviewed_finding_is_ignored_in_every_commit_of_its_line() -> None:
    lines = (ROOT / ".betterleaksignore").read_text(encoding="utf-8").splitlines()
    assert REVIEWED in lines, lines
