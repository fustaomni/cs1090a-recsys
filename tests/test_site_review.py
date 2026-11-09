# tests/test_site_review.py
"""Each page of the project site says what its source says, reviewed page by page (A.256).

THE BRIEF IS THE AUTHORITY: Milestone 2's wording is read from the requirement contract, never
typed into this proof, so the page is held to what the course asked for.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "site" / "src" / "data" / "project.json"
BRIEF = ROOT / "contracts" / "requirements" / "milestone2.md"
DELIVERABLES = (
    "8 to 10 minute presentation",
    "slides",
    ".ipynb",
    "revised proposal of one to two pages",
    "Friday, November 13 at 9:59 pm ET",
)
EDA_LATER = "Exploratory data analysis and a baseline model come in Milestone 3"


def _milestones() -> list[dict[str, object]]:
    project = json.loads(PROJECT.read_text(encoding="utf-8"))
    milestones = project.get("milestones")
    assert isinstance(milestones, list), project.keys()
    return milestones


def _brief() -> str:
    """The brief with its wrapped lines joined, so a phrase split across lines still matches."""
    return " ".join(BRIEF.read_text(encoding="utf-8").split())


def _phase_ids(milestone: dict[str, object]) -> list[str]:
    ids = milestone.get("phase_ids")
    assert isinstance(ids, list), milestone
    return [str(phase) for phase in ids]


def test_milestone_statuses_run_done_then_current_then_planned() -> None:
    """Milestone 1 has passed and Milestone 2 is under way, as the calendar stood at review."""
    milestones = _milestones()
    statuses = [str(milestone.get("status")) for milestone in nonempty(milestones)]
    current = [
        milestone.get("id") for milestone in milestones if milestone.get("status") == "current"
    ]
    assert current == ["M2"], statuses
    position = statuses.index("current")
    assert set(statuses[:position]) == {"done"}, statuses
    assert set(statuses[position + 1 :]) == {"planned"}, statuses


def test_milestone_2_is_described_and_scoped_as_the_brief_states() -> None:
    """Milestone 2's name, deliverables and deadline are the brief's; EDA waits for Milestone 3."""
    brief = _brief()
    by_id = {str(milestone.get("id")): milestone for milestone in nonempty(_milestones())}
    second, third = by_id["M2"], by_id["M3"]
    heading = re.search(r"## \[MS2\] (.+?) \[", brief)
    assert heading, "the brief names no Milestone 2"
    assert str(second.get("name")).casefold() == heading.group(1).casefold(), second
    focus = str(second.get("focus"))
    for phrase in nonempty(DELIVERABLES):
        assert phrase in brief, f"the brief no longer says {phrase!r}"
        assert phrase in focus, f"Milestone 2 omits {phrase!r}: {focus}"
    assert EDA_LATER in brief, "the brief no longer places EDA in Milestone 3"
    assert _phase_ids(second) == ["0", "1A", "2"], second
    assert _phase_ids(third)[:2] == ["1B", "3"], third
    for milestone in (second, third):
        assert milestone.get("phases") == ", ".join(_phase_ids(milestone)), milestone
