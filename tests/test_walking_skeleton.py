# tests/test_walking_skeleton.py
"""The walking skeleton carries one number from a verified archive to the proposal (A.244)."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

import milestone2
from milestone2 import ArchiveRefusedError, Results

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "milestone2.py"
ROWS = ("1::1193::5::978300760", "1::661::3::978302109", "2::1357::5::978298709")


def _archive(tmp_path: Path) -> tuple[Path, str]:
    """An archive shaped like MovieLens 1M, made here, and the digest that pins it."""
    archive = tmp_path / "ml-1m.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("ml-1m/ratings.dat", "\n".join(ROWS) + "\n")
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest()


def test_one_number_travels_from_the_verified_archive_to_a_rendered_line(tmp_path: Path) -> None:
    archive, pinned = _archive(tmp_path)
    out = tmp_path / "results.json"
    results = milestone2.run_notebook(NOTEBOOK, archive, pinned, out)
    assert results.ratings == len(ROWS), results
    assert Results.model_validate_json(out.read_text(encoding="utf-8")) == results
    line = milestone2.render_line(results)
    assert line.startswith(f"MovieLens 1M holds {len(ROWS):,} ratings"), line


def test_the_rendered_claim_traces_back_to_the_archive_digest(tmp_path: Path) -> None:
    archive, pinned = _archive(tmp_path)
    results = milestone2.run_notebook(NOTEBOOK, archive, pinned, tmp_path / "results.json")
    assert results.archive_sha256 == pinned, results
    line = milestone2.render_line(results)
    assert f"archive sha256:{pinned[:12]}" in line, line
    refused = tmp_path / "refused.json"
    with pytest.raises(ArchiveRefusedError):
        milestone2.run_notebook(NOTEBOOK, archive, "0" * 64, refused)
    assert not refused.exists()
