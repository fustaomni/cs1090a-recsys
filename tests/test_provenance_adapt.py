"""A change to a ported file is planned as its recorded, reversible patch (A.85).

provenance:adapt checks the upstream copy against the digest provenance records, builds the patch
from upstream to the working file, proves it reverses, and plans both writes as one spec.
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

import pytest

import provenance_adapt

UPSTREAM = "def answer() -> int:\n    return 41\n"
LOCAL = "def answer() -> int:\n    return 42\n"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _setup(tmp_path: Path, upstream_text: str) -> tuple[Path, Path]:
    root, upstream = tmp_path / "root", tmp_path / "upstream"
    for base, text in ((root, LOCAL), (upstream, upstream_text)):
        (base / "scripts").mkdir(parents=True)
        (base / "scripts" / "answer.py").write_text(text, encoding="utf-8")
    record = (
        'contract = "provenance/v1"\n\n[[files]]\npath = "scripts/answer.py"\n'
        f'sha256 = "{_digest(UPSTREAM)}"\n'
    )
    (root / "contracts").mkdir()
    (root / "contracts" / "provenance.toml").write_text(record, encoding="utf-8")
    return root, upstream


def test_an_adaptation_is_planned_as_a_reversible_patch(tmp_path: Path) -> None:
    root, upstream = _setup(tmp_path, UPSTREAM)
    spec = tomllib.loads(provenance_adapt.plan(root, upstream, "scripts/answer.py", "why"))
    operations = spec["operations"]
    assert [op["path"] for op in operations] == [
        "contracts/vendor-patches/scripts/answer.py.patch",
        "contracts/provenance.toml",
    ]
    patch = operations[0]["content"]
    assert provenance_adapt.reverses_to_upstream(
        "scripts/answer.py", patch, LOCAL.encode("utf-8"), _digest(UPSTREAM)
    )
    assert f'sha256 = "{_digest(LOCAL)}"' in operations[1]["replacement"]


def test_an_upstream_copy_that_differs_from_the_record_is_refused(tmp_path: Path) -> None:
    root, upstream = _setup(tmp_path, "def answer() -> int:\n    return 0\n")
    with pytest.raises(SystemExit, match="does not match the recorded upstream digest"):
        provenance_adapt.plan(root, upstream, "scripts/answer.py", "why")
