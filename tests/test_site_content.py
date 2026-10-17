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


def test_every_model_phase_has_a_family() -> None:
    data = json.loads((SITE / "src" / "data" / "project.json").read_text(encoding="utf-8"))
    missing = sorted({model["phase"] for model in data["models"]} - set(data["families"]))
    assert missing == []


def test_every_mechanism_is_registered_and_each_built_one_has_its_lab() -> None:
    """Each model and technique has a lab entry, and a built entry has its file and its loader."""
    data = json.loads((SITE / "src" / "data" / "project.json").read_text(encoding="utf-8"))
    registry = SITE / "src" / "data" / "mechanisms.json"
    labs = json.loads(registry.read_text(encoding="utf-8"))["labs"]
    models = [lab["ref"] for lab in labs if lab["kind"] == "model"]
    techniques = [lab["ref"] for lab in labs if lab["kind"] == "technique"]
    assert models == [model["id"] for model in data["models"]]
    assert techniques == [technique["id"] for technique in data["techniques"]]
    built = {lab["id"] for lab in labs if lab["status"] == "built"}
    files = {path.stem for path in (SITE / "src" / "mechanisms" / "labs").glob("*.jsx")}
    assert built == files
    loader = (SITE / "src" / "mechanisms" / "Mechanisms.jsx").read_text(encoding="utf-8")
    assert sorted(lab for lab in built if f'import("./labs/{lab}.jsx")' not in loader) == []


def test_the_site_names_members_only_in_the_group_card() -> None:
    """A group project: a person's name appears only in the group's member list."""
    data = json.loads((SITE / "src" / "data" / "project.json").read_text(encoding="utf-8"))
    members = data["group"]["members"]
    rest = json.dumps({key: value for key, value in data.items() if key != "group"})
    leaks = [name for name in members if name in rest]
    leaks += [
        f"{path.relative_to(ROOT)}: {name}"
        for path in _sources()
        if path.name != "project.json"
        for name in members
        if name in path.read_text(encoding="utf-8")
    ]
    assert leaks == []


# MovieLens's own genre name keeps the retired word; everywhere else the proposal's word is movie.
KEPT = ("film-noir",)
RETIRED = KEPT[0].split("-")[0]


def test_the_codebase_says_movie_throughout() -> None:
    """Every tracked text file uses movie; only the genre name Film-Noir keeps the old word."""
    listed = git("ls-files", "-z", cwd=ROOT).stdout.split("\0")
    found: list[str] = []
    for name in listed:
        path = ROOT / name
        if not name or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        left = text.count(RETIRED) - sum(text.count(term) for term in KEPT)
        if left:
            found.append(f"{name}: {left}")
    assert found == []


def test_every_displayed_fitted_parameter_carries_its_provenance() -> None:
    """A.100: each lab shows where its fitted numbers came from, beside the numbers."""
    labs = sorted((SITE / "src" / "mechanisms" / "labs").glob("*.jsx"))
    assert labs, "the site has no labs to check"
    missing = [lab.name for lab in labs if "<Provenance" not in lab.read_text(encoding="utf-8")]
    assert missing == []


def test_the_movielens_summary_is_computed_from_the_verified_ratings() -> None:
    """A.100: the site's real numbers come from the bytes the baseline model is pinned to."""
    baseline = (SITE.parent / "contracts" / "model-runs" / "baseline.toml").read_text("utf-8")
    pinned = next(
        line.split('"')[1] for line in baseline.splitlines() if line.startswith("data_sha256 = ")
    )
    summary = (SITE / "src" / "data" / "movielens.json").read_text("utf-8")
    assert f'"ratings.dat":"{pinned}"' in summary


def test_the_site_data_carries_every_phase_model_and_technique() -> None:
    data = json.loads((SITE / "src" / "data" / "project.json").read_text(encoding="utf-8"))
    assert [phase["id"] for phase in data["phases"]] == PHASES
    assert [model["id"] for model in data["models"]] == list(range(1, 13))
    assert len(data["baselines"]) == 4
    assert len(data["techniques"]) == 10
