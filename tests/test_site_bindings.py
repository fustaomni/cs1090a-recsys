# tests/test_site_bindings.py
"""The project site holds no typed-in data: every figure is bound to its source (A.245)."""

from __future__ import annotations

import json
import re
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
