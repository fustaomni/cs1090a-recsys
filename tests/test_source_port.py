"""source:port plans a port as a source:apply spec, and writes nothing itself (A.29)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import source_port


def _checkouts(tmp_path: Path) -> tuple[Path, Path]:
    source, here = tmp_path / "source", tmp_path / "here"
    (source / "scripts").mkdir(parents=True)
    (here / "contracts").mkdir(parents=True)
    (here / "contracts" / "provenance.toml").write_text('contract = "x"\n', encoding="utf-8")
    return source, here


def test_an_upstream_file_becomes_a_create_spec(tmp_path: Path) -> None:
    source, here = _checkouts(tmp_path)
    (source / "scripts" / "a.py").write_text('"""A."""\n', encoding="utf-8")
    spec = tomllib.loads(source_port.build(source, ["scripts/a.py"], here))
    create, record = spec["operations"]
    assert (create["op"], create["path"]) == ("create", "scripts/a.py")
    assert create["content"] == '"""A."""\n'
    assert record["path"] == "contracts/provenance.toml"
    assert 'path = "scripts/a.py"' in record["replacement"]
    assert not (here / "scripts" / "a.py").exists(), "planning must write nothing"


def test_a_file_already_present_is_refused(tmp_path: Path) -> None:
    source, here = _checkouts(tmp_path)
    (source / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (here / "scripts").mkdir()
    (here / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="already present"):
        source_port.build(source, ["scripts/a.py"], here)


def test_a_python_line_over_the_limit_is_refused_before_emitting(tmp_path: Path) -> None:
    source, here = _checkouts(tmp_path)
    (source / "scripts" / "a.py").write_text("x = 1  # " + "y" * 100 + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="over 100 columns"):
        source_port.build(source, ["scripts/a.py"], here)
