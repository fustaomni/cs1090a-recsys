# tests/test_site_bindings.py
"""The project site holds no typed-in data: every figure is bound to its source (A.245)."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = SITE / "src" / "data"
MEMBERS = ["Thanh Phong Le", "Myra Puruganan", "Sandra Palomo"]
TITLE = "A recommender that records why it recommended, and is judged on it"
JOIN_PHRASES = ("Open seat", "Join the team", "Two seats left", "mailto:")
SOURCES = {"ratings", "users", "moviesRated", "models", "techniques", "milestones"}
COUNT_WORDS = re.compile(r"\b(ten|eleven|twelve|thirteen|fourteen)\b", re.IGNORECASE)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _load(name: str) -> dict[str, object]:
    loaded: dict[str, object] = json.loads((DATA / name).read_text(encoding="utf-8"))
    return loaded


def _texts(value: object) -> list[str]:
    """Every string a JSON document holds, at any depth."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _texts(item)]
    if isinstance(value, list):
        return [text for item in value for text in _texts(item)]
    return []


def _figures() -> set[str]:
    """The MovieLens figures, as digits with and without their thousands separator."""
    summary = _load("movielens.json")
    structure = summary.get("structure")
    assert isinstance(structure, dict), summary
    counts = [structure[key] for key in ("ratings", "users", "moviesRated", "moviesListed")]
    return {form for count in counts for form in (str(count), f"{count:,}")}


def test_the_group_is_three_members_with_its_mentor_and_first_meeting() -> None:
    data = _load("project.json")
    group = data.get("group")
    assert isinstance(group, dict), data
    assert group.get("members") == MEMBERS, group
    assert group.get("mentor") == "Sukanya Krishna", group
    assert group.get("first_meeting") == "Friday, November 13, 2026, at 7:00 PM ET", group
    assert "seats" not in group, group
    assert data.get("title") == TITLE, data.get("title")


def test_no_join_call_or_open_seat_remains() -> None:
    assert "join" not in _load("project.json")
    sources = [*sorted((SITE / "src").rglob("*.js*")), SITE / "index.html"]
    found = [
        f"{path.relative_to(ROOT)}: {phrase}"
        for path in nonempty(sources)
        for phrase in JOIN_PHRASES
        if phrase in path.read_text(encoding="utf-8")
    ]
    assert found == [], found


def test_every_count_on_the_page_is_derived_from_its_source() -> None:
    overview = _load("project.json").get("overview")
    assert isinstance(overview, dict), overview
    stats = overview.get("stats")
    assert isinstance(stats, list), overview
    typed = [stat for stat in nonempty(stats) if set(stat) != {"bind", "label"}]
    assert typed == [], typed
    assert {stat["bind"] for stat in stats} <= SOURCES, stats


def test_a_number_typed_into_the_site_text_is_refused() -> None:
    texts = _texts(_load("project.json"))
    texts.append((SITE / "src" / "App.jsx").read_text(encoding="utf-8"))
    figures = _figures()
    typed = [
        text[:80]
        for text in nonempty(texts)
        if COUNT_WORDS.search(text)
        or any(re.search(rf"(?<![0-9,.]){re.escape(figure)}(?![0-9,])", text) for figure in figures)
    ]
    assert typed == [], typed


def test_each_milestone_has_a_results_section_filled_only_from_recorded_evidence() -> None:
    milestones = _load("project.json").get("milestones")
    assert isinstance(milestones, list), milestones
    results = _load("results.json")
    sections = results.get("milestones", [])
    assert isinstance(sections, list), results
    assert [section.get("milestone") for section in sections] == [
        milestone["id"] for milestone in nonempty(milestones)
    ], sections
    entries = [entry for section in sections for entry in section.get("entries", [])]
    unrecorded = [
        entry
        for entry in entries
        if not SHA256.match(str(entry.get("evidence", {}).get("sha256", "")))
        or not entry.get("evidence", {}).get("contract")
    ]
    assert unrecorded == [], unrecorded


def test_the_group_card_names_the_next_meeting() -> None:
    """A.343: the card shows the next meeting from data; the first meeting stays recorded."""
    group = _load("project.json").get("group")
    assert isinstance(group, dict), group
    assert group.get("next_meeting") == {"label": "Milestone 3 TF Meeting", "when": "TBD"}, group
    app = (SITE / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "group.next_meeting.label" in app, "the card does not render the next meeting"
    assert "First TF Meeting:" not in app, "the card still names the first meeting"


def test_the_delivered_milestones_are_done_and_the_next_is_current() -> None:
    """A.343: Milestones 1 and 2 are delivered and 3 is current; no status says otherwise."""
    data = _load("project.json")
    milestones = data.get("milestones")
    assert isinstance(milestones, list), milestones
    states = {entry["id"]: entry["status"] for entry in nonempty(milestones)}
    assert states == {"M1": "done", "M2": "done", "M3": "current", "M4": "planned"}, states
    assert "under way" not in str(data.get("status")), data.get("status")


def test_the_protocol_separates_what_ran_from_what_is_planned() -> None:
    """A.343: the header names the split Milestone 2 ran apart from what Milestone 3 plans."""
    protocol = str(_load("results.json").get("protocol"))
    assert "Milestone 2" in protocol, protocol
    assert "Milestone 3" in protocol and "planned" in protocol, protocol


def test_the_mixture_of_experts_is_listed_from_data() -> None:
    """A.346: the MoE is listed from data with its shared expert, specialists and gate."""
    models = _load("project.json").get("models")
    assert isinstance(models, list), models
    moe = next((m for m in models if m.get("name") == "Gated mixture of experts"), None)
    assert moe is not None, [m.get("name") for m in models]
    assert moe.get("experts") == {
        "shared": "Regularised bias model",
        "specialists": ["Movie mean", "Regularised linear regression", "kNN regression"],
    }, moe
    assert moe.get("gate") == "softmax over features computed strictly before the rating", moe


def test_the_m2_results_are_recorded_from_the_notebook_run() -> None:
    """A.344: M2 shows every label its pointers file names, all read from one recorded run."""
    pointers = ROOT / "contracts" / "site-sections" / "M2.toml"
    labels = list(tomllib.loads(pointers.read_text(encoding="utf-8"))["pointers"])
    assert labels, "the M2 pointers file names no label"
    sections = _load("results.json").get("milestones")
    assert isinstance(sections, list), sections
    section = next(entry for entry in sections if entry.get("milestone") == "M2")
    entries = section.get("entries", [])
    assert [entry.get("label") for entry in entries] == labels, entries
    digests = {entry["evidence"]["sha256"] for entry in nonempty(entries)}
    contracts = {entry["evidence"]["contract"] for entry in entries}
    assert len(digests) == 1 and contracts == {"milestone2-results/v1"}, (digests, contracts)


QUALITY_RULES = 5


def test_the_m2_findings_are_recorded_from_the_notebook_run() -> None:
    """A.349: M2 shows each ratings-quality/v1 finding's count, read by its pointer from the run."""
    pointers = ROOT / "contracts" / "site-sections" / "M2.toml"
    named = set(tomllib.loads(pointers.read_text(encoding="utf-8"))["pointers"].values())
    wanted = [f"/quality/{rule}/count" for rule in range(QUALITY_RULES)]
    wanted += [f"/quality/{rule}/status" for rule in range(QUALITY_RULES)]
    missing = [pointer for pointer in wanted if pointer not in named]
    assert missing == [], missing


SPLIT_WINDOWS = ("train", "validation", "test")
SPLIT_FIELDS = ("ratings", "users", "movies", "first", "last")


def test_the_split_audit_is_recorded_from_the_notebook_run() -> None:
    """A.350: M2 shows each split window and the leakage verdict, each read from the run."""
    pointers = ROOT / "contracts" / "site-sections" / "M2.toml"
    named = set(tomllib.loads(pointers.read_text(encoding="utf-8"))["pointers"].values())
    wanted = ["/split_audit/leakage"] + [
        f"/split_audit/windows/{window}/{field}"
        for window in SPLIT_WINDOWS
        for field in SPLIT_FIELDS
    ]
    missing = [pointer for pointer in wanted if pointer not in named]
    assert missing == [], missing


def _ms2(pointer: str) -> object:
    """One value the notebook recorded for Milestone 2, read from Results by its pointer."""
    sections = _load("results.json").get("milestones")
    assert isinstance(sections, list), sections
    section = next(entry for entry in sections if entry.get("milestone") == "M2")
    found = [entry["value"] for entry in section["entries"] if entry.get("pointer") == pointer]
    assert len(found) == 1, (pointer, found)
    return found[0]


QUANTILE_TOKENS = ("ms2ValidationQuantile", "ms2TestQuantile")
TYPED_QUANTILE = re.compile(r"\b0\.\d+\b")


def test_the_overview_quantile_claim_follows_the_data() -> None:
    """A.350: Milestone 2's cut quantiles are bound from the recorded windows, never typed."""
    counts = [_ms2(f"/split_audit/windows/{window}/ratings") for window in SPLIT_WINDOWS]
    assert all(isinstance(count, int) and count > 0 for count in nonempty(counts)), counts
    project = _load("project.json")
    phases = project.get("phases")
    assert isinstance(phases, list), project.keys()
    phase = next(entry for entry in phases if entry.get("id") == "2")
    claims = [point for point in nonempty(phase["points"]) if "Milestone 2" in point]
    assert len(claims) == 1, claims
    milestone_2 = claims[0].split("Milestone 3")[0]
    missing = [token for token in QUANTILE_TOKENS if f"{{{token}}}" not in milestone_2]
    assert missing == [], (missing, milestone_2)
    assert not TYPED_QUANTILE.search(milestone_2), milestone_2
    binder = (SITE / "src" / "bind.js").read_text(encoding="utf-8")
    assert 'import results from "./data/results.json";' in binder, "bind.js reads no results"
    unbound = [token for token in QUANTILE_TOKENS if f"{token}:" not in binder]
    assert unbound == [], unbound
    assert "/split_audit/windows/" in binder, "the quantiles are not read from the split audit"
