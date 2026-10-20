# tests/test_source_port_relocate.py
"""A port may land at another path, and records the path it came from (A.123).

This repository declares a test's level by its directory (A.39), so a port can need a new place,
and provenance must still name the upstream file its bytes came from.
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

from source_port import build


def test_a_port_placed_elsewhere_records_its_upstream_path(tmp_path: Path) -> None:
    source, here = tmp_path / "upstream", tmp_path / "here"
    (source / "tests").mkdir(parents=True)
    (source / "tests" / "t.py").write_text("x = 1\n", encoding="utf-8")
    (here / "contracts").mkdir(parents=True)
    (here / "contracts" / "provenance.toml").write_text('commit = "c"\n', encoding="utf-8")
    spec = tomllib.loads(build(source, ["tests/t.py=tests/integration/t.py"], here))
    created = [op["path"] for op in spec["operations"] if op["op"] == "create"]
    assert created == ["tests/integration/t.py"]
    record = tomllib.loads(spec["operations"][-1]["replacement"])
    digest = hashlib.sha256(b"x = 1\n").hexdigest()
    assert record["files"] == [
        {"path": "tests/integration/t.py", "upstream_path": "tests/t.py", "sha256": digest}
    ]
