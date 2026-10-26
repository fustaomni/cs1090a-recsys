"""source:port plans a port into another checkout, the canonical source included (A.217).

Centralizing a sibling's capability means planning its files into the canonical source, which
keeps no port record: its files are its own. --into names the destination; the plan is judged
against that tree and saved where that checkout's own source:apply reads it.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

import source_port


def _canonical(tmp_path: Path) -> tuple[Path, Path]:
    """A source with scripts/, and a destination that keeps no port record, as cscie103 does."""
    source, into = tmp_path / "source", tmp_path / "into"
    (source / "scripts").mkdir(parents=True)
    (into / "scripts").mkdir(parents=True)
    return source, into


def test_a_port_into_a_canonical_source_creates_its_files_only(tmp_path: Path) -> None:
    """Without a port record in the destination, the plan creates the file and records nothing."""
    source, into = _canonical(tmp_path)
    (source / "scripts" / "a.py").write_text('"""A."""\n', encoding="utf-8")
    try:
        spec = tomllib.loads(source_port.build(source, ["scripts/a.py"], into))
    except FileNotFoundError as missing:
        pytest.fail(f"a destination without a port record was refused: {missing}")
    operations = [(entry["op"], entry["path"]) for entry in spec["operations"]]
    assert operations == [("create", "scripts/a.py")], operations


def test_a_planned_spec_is_saved_under_the_destinations_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--into with --out writes the plan where the destination's source:apply reads it."""
    source, into = _canonical(tmp_path)
    (source / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(source_port, "ROOT", home)
    out = ".artifacts/port/a.toml"
    argv = ["source_port.py", "--into", str(into), "--out", out, str(source), "scripts/a.py"]
    monkeypatch.setattr(sys, "argv", argv)
    try:
        assert source_port.main() == 0
    except (SystemExit, FileNotFoundError) as refused:
        pytest.fail(f"--into was not understood: {refused}")
    saved = (into / ".artifacts" / "port" / "a.toml").read_text(encoding="utf-8")
    assert tomllib.loads(saved)["operations"][0]["path"] == "scripts/a.py"
    assert not (home / ".artifacts").exists(), "nothing is written into this checkout"


def test_a_file_present_in_the_destination_is_refused(tmp_path: Path) -> None:
    """Already present is judged against the destination's tree, not this checkout's."""
    source, into = _canonical(tmp_path)
    (source / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (into / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
    try:
        with pytest.raises(SystemExit, match="already present"):
            source_port.build(source, ["scripts/a.py"], into)
    except FileNotFoundError as missing:
        pytest.fail(f"the destination's tree was never judged: {missing}")
