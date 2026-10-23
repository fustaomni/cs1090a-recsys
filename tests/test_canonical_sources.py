"""Tracked references name each upstream where it lives, never through a redirect (A.183).

cscie103 moved from ltphongssvn to fustaomni. GitHub redirects the old location, but a redirect
ends silently once anything is created there, so a tracked file names the canonical one. A
vendor patch and the plan trace are exempt: each quotes history, never a live reference. Only
tracked files are read, listed as the hygiene gate lists them, so no cache or artifact is judged.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from check_repo_hygiene import tracked_files

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = "https://github.com/fustaomni/cscie103-data-engineering"
RETIRED = "ltphongssvn/cscie103"
QUOTED = (ROOT / "contracts" / "vendor-patches", ROOT / "context" / "plan-trace.toml")


def _naming_the_retired_location() -> list[str]:
    here = Path(__file__).resolve()
    tracked = [ROOT / path for path in tracked_files()]
    read = [path for path in tracked if path.is_file() and path != here]
    live = [path for path in read if not any(path.is_relative_to(q) for q in QUOTED)]
    assert live, "no tracked file was read"
    return [
        str(path.relative_to(ROOT))
        for path in live
        if RETIRED in path.read_text(encoding="utf-8", errors="ignore")
    ]


def test_tracked_references_name_cscie103_where_it_lives() -> None:
    record = tomllib.loads((ROOT / "contracts" / "provenance.toml").read_text(encoding="utf-8"))
    assert record["source"] == CANONICAL, record["source"]
    assert _naming_the_retired_location() == [], _naming_the_retired_location()
