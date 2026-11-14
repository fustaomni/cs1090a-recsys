# A.311: the practical threshold is declared before any result is seen.

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = ROOT / "contracts" / "practical-threshold.toml"
RESULTS = ROOT / "site" / "src" / "data" / "results.json"
FIELDS = (
    "method",
    "anchor",
    "sources",
    "formula",
    "sensitivity",
    "detectability",
    "decided_by",
    "declared_at",
)


def test_the_threshold_is_declared_before_any_result() -> None:
    # A.311: a complete, dated declaration exists while the primary verdict is still empty.
    assert DECLARATION.is_file(), "no practical-threshold declaration is committed"
    record = tomllib.loads(DECLARATION.read_text(encoding="utf-8"))
    missing = [field for field in FIELDS if not record.get(field)]
    assert not missing, missing
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    verdict = results["primary"].get("verdict")
    assert not verdict, f"a verdict exists before the declaration: {verdict}"
