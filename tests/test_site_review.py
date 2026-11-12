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


def test_every_lab_is_titled_by_its_model_or_technique_number() -> None:
    """Each lab's heading is bound from the data as Model N or Technique N, in its order (A.260)."""
    project = _project()
    mechanisms = ROOT / "site" / "src" / "mechanisms"
    registry = json.loads((PROJECT.parent / "mechanisms.json").read_text(encoding="utf-8"))
    expected = [("model", model["id"]) for model in project["models"]] + [
        ("technique", technique["id"]) for technique in project["techniques"]
    ]
    labs = nonempty(registry["labs"])
    assert [(lab["kind"], lab["ref"]) for lab in labs] == expected, labs
    for lab in nonempty(labs):
        assert lab["id"] == f"{lab['kind'][0].upper()}{lab['ref']}", lab
    files = nonempty(sorted((mechanisms / "labs").glob("*.jsx")))
    typed = [path.name for path in files if "<h3>" in path.read_text(encoding="utf-8")]
    assert typed == [], typed
    page = (mechanisms / "Mechanisms.jsx").read_text(encoding="utf-8")
    assert "{bind(`{${current.kind}:${current.ref}}`)}" in page, "the lab heading is not bound"


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


# A.282: THE EVIDENCE CHAIN, stated once on the Overview page and read from project.json.
CHAIN = ("Policy as code", "Evidence as data", "Evaluator", "Verdict", "Decision", "Enforcement")
OUT_OF_SCOPE = "outside the TF's scope"
STATUSES = {"in place", "planned", OUT_OF_SCOPE}
PLAN = ROOT / "context" / "plan.toml"


def _evidence() -> dict[str, Any]:
    evidence = _project().get("evidence")
    assert isinstance(evidence, dict), "project.json states no evidence chain"
    return evidence


def test_the_evidence_chain_is_stated_on_the_overview_page_only() -> None:
    """The chain is stated once, on Overview; the other pages would only repeat it."""
    evidence = _evidence()
    assert tuple(evidence["chain"]) == CHAIN, evidence["chain"]
    assert set(evidence["pages"]) == {"overview"}, sorted(evidence["pages"])
    overview = evidence["pages"]["overview"]
    assert overview["note"], overview
    known = {discipline["id"] for discipline in nonempty(evidence["disciplines"])}
    assert set(nonempty(overview["disciplines"])) == known, overview["disciplines"]
    source = ROOT / "site" / "src"
    app = (source / "App.jsx").read_text(encoding="utf-8")
    labs = (source / "mechanisms" / "Mechanisms.jsx").read_text(encoding="utf-8")
    assert app.count("<EvidenceChain") == 1, "the chain is rendered on more than Overview"
    assert '<EvidenceChain page="overview" />' in app, "Overview omits the chain"
    assert "EvidenceChain" not in labs, "Interactive mechanisms repeats the chain"


def test_every_discipline_names_its_status_and_its_step_or_why_it_is_out_of_scope() -> None:
    """Seven disciplines: a planned one names steps the plan holds, an excluded one its reason."""
    plan = PLAN.read_text(encoding="utf-8")
    disciplines = nonempty(_evidence()["disciplines"])
    assert len(disciplines) == 7, [discipline["name"] for discipline in disciplines]
    for discipline in disciplines:
        assert discipline["status"] in STATUSES, discipline
        assert discipline["question"] and discipline["now"], discipline
        if discipline["status"] == OUT_OF_SCOPE:
            assert discipline["why"], discipline
            continue
        for step in nonempty(discipline["steps"]):
            assert f'id = "{step}"' in plan, (step, discipline["name"])


# A.290: THE FIRST TF MEETING, as scheduled.
FIRST_MEETING = "Friday, November 13, 2026, at 7:00 PM ET"


def test_the_project_card_names_the_first_tf_meeting() -> None:
    # The card names the scheduled first TF meeting, never TBD.
    meeting = _project()["group"]["first_meeting"]
    assert meeting == FIRST_MEETING, meeting


def test_every_industry_practice_names_its_step_or_why_it_is_out_of_scope() -> None:
    # A.294: each practice names steps the plan holds, or why it is outside the TF's scope.
    plan = PLAN.read_text(encoding="utf-8")
    practices = _evidence().get("practices")
    assert isinstance(practices, list), "Overview lists no industry practice"
    for practice in nonempty(practices):
        assert practice["org"] and practice["practice"] and practice["here"], practice
        if practice["status"] == OUT_OF_SCOPE:
            assert practice["why"], practice
            continue
        assert practice["status"] == "planned", practice
        for step in nonempty(practice["steps"]):
            assert f'id = "{step}"' in plan, (step, practice["org"])
    chain = (ROOT / "site" / "src" / "EvidenceChain.jsx").read_text(encoding="utf-8")
    assert "evidence.practices.map" in chain, "Overview does not render the practices"


def test_results_state_that_prediction_is_not_causal_value() -> None:
    # A.294: Results says a well-predicted rating is not evidence that recommending adds value.
    note = _evidence().get("prediction_note")
    assert isinstance(note, str), "Results states no prediction note"
    assert "not evidence" in note, note
    app = (ROOT / "site" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "{data.evidence.prediction_note}" in app, "Results omits the prediction note"
