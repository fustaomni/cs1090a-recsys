# tests/test_site_review.py
"""Each page of the project site says what its source says, reviewed page by page (A.256).

THE BRIEF IS THE AUTHORITY: Milestone 2's wording is read from the requirement contract, never
typed into this proof, so the page is held to what the course asked for.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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
# THE SCOPE AS REVIEWED (A.257): asserted content, so a later change to it is a reviewed one.
REMOVED = {
    "The live application, serving and latency budget": (
        "Building a live application exceeds the project scope"
    ),
    "Real-user impression logging and off-policy evaluation": (
        "Live-user data would not meet the public-data requirement"
    ),
    "The Open Bandit Dataset": "Analysing a second large dataset exceeds the scope",
    "The self-attention sequence model": "Outside the chosen family of methods",
}
RETAINED = {
    "MovieLens 1M, offline only": ("{ratings}", "{users}", "{moviesRated}"),
    "Predicting the next recorded rating": ("never a movie watched",),
    "Tabular inputs, classical methods": ("{models}", "{techniques}"),
}
PRINCIPLE = "Every question, feature and metric concerns rating submissions."


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


def _scope_entries(key: str) -> list[dict[str, object]]:
    project = json.loads(PROJECT.read_text(encoding="utf-8"))
    scope = project.get("scope")
    assert isinstance(scope, dict), project.keys()
    entries = scope.get(key)
    assert isinstance(entries, list), scope
    return entries


def test_scope_holds_what_the_review_confirmed() -> None:
    """The reviewed Scope: four removals with reasons, three retentions bound to their counts."""
    gone = {str(e.get("item")): str(e.get("why")) for e in nonempty(_scope_entries("removed"))}
    assert gone == REMOVED, gone
    kept = {str(e.get("item")): str(e.get("form")) for e in nonempty(_scope_entries("retained"))}
    assert set(kept) == set(RETAINED), kept
    for item, required in nonempty(RETAINED.items()):
        for phrase in nonempty(required):
            assert phrase in kept[item], (item, kept[item])
    project = json.loads(PROJECT.read_text(encoding="utf-8"))
    principle = str(project["scope"]["principle"])
    assert principle.endswith(PRINCIPLE), principle


# A.258: EVERY MODEL AND TECHNIQUE IS A BINDING, never typed: {model:N} and {technique:N}.
WHERE = re.compile(r"Phases? (\d+[AB]?(?:(?:, | and )\d+[AB]?)*)")
TYPED = re.compile(r"\b(?:[Mm]odel|[Tt]echnique)s? \d+\b")


def _project() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(PROJECT.read_text(encoding="utf-8"))
    return loaded


def _phase_points(project: dict[str, Any]) -> dict[str, list[str]]:
    return {str(phase["id"]): list(phase["points"]) for phase in nonempty(project["phases"])}


def _where_phases(where: str) -> list[str]:
    """The phase ids a technique's where names: "Phases 1A and 1B, ..." gives 1A and 1B."""
    found = [part for run in WHERE.findall(where) for part in re.split(r", | and ", run)]
    assert found, f"no phase named in: {where}"
    return found


def test_every_model_is_named_by_number_in_the_phase_the_data_places_it() -> None:
    """Every model is bound by number in the points of the phase its data names."""
    project = _project()
    points = _phase_points(project)
    missing = [
        f"Model {model['id']} in Phase {model['phase']}"
        for model in nonempty(project["models"])
        if not any(f"{{model:{model['id']}}}" in point for point in points[str(model["phase"])])
    ]
    assert missing == [], missing


def test_every_technique_is_named_by_number_in_each_phase_it_names() -> None:
    """Every technique is bound by number in each phase its where names."""
    project = _project()
    points = _phase_points(project)
    missing = [
        f"Technique {technique['id']} in Phase {phase}"
        for technique in nonempty(project["techniques"])
        for phase in _where_phases(str(technique["where"]))
        if not any(f"{{technique:{technique['id']}}}" in point for point in points[phase])
    ]
    assert missing == [], missing


def test_the_baseline_note_names_its_model_by_binding() -> None:
    """The baseline note names Model 12 by binding, never as a typed number or ordinal (A.259)."""
    note = _project()["baseline_note"]
    assert "{model:12}" in note, note
    assert not TYPED.search(note) and "twelfth" not in note, note
    app = (ROOT / "site" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "{bind(data.baseline_note)}" in app, "the baseline note is rendered without bind"


def test_a_typed_model_or_technique_reference_is_refused() -> None:
    """No phase point types a model or technique number; each is a binding instead."""
    points = _phase_points(_project())
    typed = [
        f"Phase {phase}: {point[:60]}"
        for phase, texts in nonempty(points.items())
        for point in texts
        if TYPED.search(point)
    ]
    assert typed == [], typed
