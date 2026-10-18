"""No ported path is recorded twice in provenance (A.85).

An array of tables accepts any number of entries, and a reader keyed by path keeps the last, so a
second entry for one path would silently shadow the first. Each path appears at most once among
the ported files and at most once among the adaptations.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from pathlib import Path

RECORD = Path(__file__).resolve().parent.parent / "contracts" / "provenance.toml"


def test_no_path_is_recorded_twice() -> None:
    record = tomllib.loads(RECORD.read_text(encoding="utf-8"))
    for table in ("files", "adapted"):
        counts = Counter(entry["path"] for entry in record.get(table, []))
        assert [path for path, seen in counts.items() if seen > 1] == [], table
