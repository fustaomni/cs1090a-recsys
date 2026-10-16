"""The project site renders the design from one data file, and names no course material (A.95)."""

from __future__ import annotations

import json
from pathlib import Path

from gitenv import git

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
FORBIDDEN = ("course material", "lecture", "deck")
SOURCES = {".json", ".jsx", ".js", ".html", ".css", ".md"}
PHASES = ["0", "1A", "2", "1B", *[str(number) for number in range(3, 14)]]


def _sources() -> list[Path]:
    skipped = {"node_modules", "dist"}
    return [
        path
        for path in sorted(SITE.rglob("*"))
        if path.is_file()
        and path.suffix in SOURCES
        and path.name != "package-lock.json"
        and not skipped & set(path.parts)
    ]


def test_the_site_names_no_course_material() -> None:
    sources = _sources()
    assert sources, "the site has no source files to check"
    found = [
        f"{path.relative_to(ROOT)}: {term}"
        for path in sources
        for term in FORBIDDEN
        if term in path.read_text(encoding="utf-8").lower()
    ]
    assert found == []


def test_no_site_source_is_ignored() -> None:
    """An ignore rule that hides a deliverable fails nothing until a commit; this fails first."""
    sources = [*_sources(), SITE / "package-lock.json"]
    assert sources, "the site has no source files to check"
    ignored = [
        str(path.relative_to(ROOT))
        for path in sources
        if git("check-ignore", "-q", str(path), cwd=ROOT).returncode == 0
    ]
    assert ignored == []


def test_every_phase_belongs_to_exactly_one_milestone() -> None:
    data = json.loads((SITE / "src" / "data" / "project.json").read_text(encoding="utf-8"))
    placed = [phase for milestone in data["milestones"] for phase in milestone["phase_ids"]]
    assert sorted(placed) == sorted(PHASES)


def test_the_site_data_carries_every_phase_model_and_technique() -> None:
    data = json.loads((SITE / "src" / "data" / "project.json").read_text(encoding="utf-8"))
    assert [phase["id"] for phase in data["phases"]] == PHASES
    assert [model["id"] for model in data["models"]] == list(range(1, 13))
    assert len(data["baselines"]) == 4
    assert len(data["techniques"]) == 10
