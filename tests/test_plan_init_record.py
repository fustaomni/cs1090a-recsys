# tests/test_plan_init_record.py
"""A day-one plan accepts its first recorded source (recsys founding F6c).

plan:init wrote the trace's sources as an array of tables, while plan:record edits an inline
array, so the first plan:record on a fresh plan was refused. Both writers now share the inline
layout cscie103's own trace is written in.
"""

from __future__ import annotations

from pathlib import Path

from plan_edit import record
from plan_init import write_day_one

NEWLINE = chr(10)


def test_a_day_one_plan_accepts_its_first_recorded_source(tmp_path: Path) -> None:
    write_day_one(tmp_path)
    spec = tmp_path / "record.toml"
    lines = (
        "[[sources]]",
        'id = "SESSION"',
        'title = "a session"',
        'locator = "a transcript"',
        "",
        "[[candidates]]",
        'source = "SESSION"',
        'ref = "r"',
        'text = "t"',
        'maps_to = ["A.1"]',
    )
    spec.write_text(NEWLINE.join(lines) + NEWLINE, encoding="utf-8")
    assert record([str(spec)], root=tmp_path) == 0
