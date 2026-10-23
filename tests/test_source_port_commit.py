# tests/test_source_port_commit.py
"""A port read at a commit other than the pin records that commit on its entry (A.136).

provenance.toml's header says each file is recorded at the commit it was read, but it held one
file-wide commit, so a file ported from a later upstream commit would claim the pin falsely.
Per-entry vendoring locks record each entry's resolved commit beside its content hash.
"""

from __future__ import annotations

import hashlib
import subprocess
import tomllib
from pathlib import Path

import source_port

PATH = "scripts/tool.py"
TEXT = "x = 1\n"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _source(tmp_path: Path) -> tuple[Path, str]:
    """A git checkout holding one file at one commit, as upstream:checkout leaves one."""
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    (source / PATH).write_text(TEXT, encoding="utf-8")
    _git(source, "init", "-q", "-b", "develop")
    _git(source, "add", ".")
    _git(source, "commit", "-q", "-m", "tool")
    return source, _git(source, "rev-parse", "HEAD")


def _here(tmp_path: Path, pinned: str) -> Path:
    here = tmp_path / "here"
    (here / "contracts").mkdir(parents=True)
    record = f'contract = "provenance/v1"\ncommit = "{pinned}"\n'
    (here / "contracts" / "provenance.toml").write_text(record, encoding="utf-8")
    return here


def _entries(spec: str) -> list[dict[str, object]]:
    """The [[files]] entries the planned spec would leave in the record."""
    operations = tomllib.loads(spec)["operations"]
    record = next(op for op in operations if op["path"] == "contracts/provenance.toml")
    return list(tomllib.loads(record["replacement"])["files"])


def test_a_port_from_another_commit_records_that_commit(tmp_path: Path) -> None:
    source, head = _source(tmp_path)
    here = _here(tmp_path, "0" * 40)
    entries = _entries(source_port.build(source, [PATH], here))
    digest = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()
    assert entries == [{"path": PATH, "sha256": digest, "commit": head}], entries


def test_a_port_from_the_pinned_commit_records_none(tmp_path: Path) -> None:
    source, head = _source(tmp_path)
    here = _here(tmp_path, head)
    entries = _entries(source_port.build(source, [PATH], here))
    assert [entry for entry in entries if "commit" in entry] == [], entries
