# tests/test_site_additions.py
"""Models 13 and 14 and techniques 11 and 12 are on the site, each with its lab (A.246)."""

from __future__ import annotations

import json
from pathlib import Path

from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = SITE / "src" / "data"
MECHANISMS = SITE / "src" / "mechanisms"
# THE DESIGN'S REQUIRED SET (A.223, A.246): fourteen models and twelve techniques.
MODELS = list(range(1, 15))
TECHNIQUES = list(range(1, 13))
ADDITIONS = ("M13", "M14", "T11", "T12")


def _load(name: str) -> dict[str, object]:
    loaded: dict[str, object] = json.loads((DATA / name).read_text(encoding="utf-8"))
    return loaded


def _labs() -> dict[str, dict[str, object]]:
    registry = _load("mechanisms.json")
    labs = registry.get("labs")
    assert isinstance(labs, list), registry
    return {str(lab["id"]): lab for lab in nonempty(labs)}


def test_the_site_carries_every_required_model_and_technique_from_its_data() -> None:
    data = _load("project.json")
    models = data.get("models")
    techniques = data.get("techniques")
    assert isinstance(models, list) and isinstance(techniques, list), data.keys()
    assert [model["id"] for model in models] == MODELS, models
    assert [technique["id"] for technique in techniques] == TECHNIQUES, techniques
    registered = set(_labs())
    required = {f"M{ref}" for ref in MODELS} | {f"T{ref}" for ref in TECHNIQUES}
    assert required <= registered, sorted(required - registered)


def test_each_addition_has_a_built_lab() -> None:
    labs = _labs()
    loader = (MECHANISMS / "Mechanisms.jsx").read_text(encoding="utf-8")
    missing = [
        lab_id
        for lab_id in nonempty(ADDITIONS)
        if labs.get(lab_id, {}).get("status") != "built"
        or not (MECHANISMS / "labs" / f"{lab_id}.jsx").is_file()
        or f'import("./labs/{lab_id}.jsx")' not in loader
    ]
    assert missing == [], missing


def test_ordinal_regression_is_a_model_not_an_exclusion() -> None:
    data = _load("project.json")
    models = data.get("models")
    assert isinstance(models, list), data.keys()
    assert any("ordinal" in str(model["name"]).lower() for model in nonempty(models)), models
    excluded = data.get("excluded", [])
    assert isinstance(excluded, list), excluded
    assert [entry for entry in excluded if "ordinal" in str(entry).lower()] == [], excluded
