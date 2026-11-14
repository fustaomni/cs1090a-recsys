# tests/test_ms2_execute.py
"""ms2:execute runs the Milestone 2 notebook on verified data and saves its outputs (A.329).

The submitted notebook must show its findings on the real MovieLens 1M, which the committed copy
does not carry. This runs it as 2026 practice trusts a notebook, in batch in a fresh kernel, and
saves the executed copy beside its results; a folder without the three tables is refused first.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import nbformat
import pytest

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "milestone2.ipynb"
USERS = ("1::F::1::10::48067", "2::M::56::16::70072")
MOVIES = (
    "1193::One Flew Over the Cuckoo's Nest (1975)::Drama",
    "661::James and the Giant Peach (1996)::Animation|Children's|Musical",
    "1357::Shine (1996)::Drama|Romance",
)
RATINGS = (
    "1::1193::5::978300760",
    "1::661::3::978302109",
    "1::1357::4::978300100",
    "2::1357::5::978298709",
    "2::1193::4::978299000",
    "2::661::2::978301000",
)


def _subject() -> ModuleType:
    found = importlib.util.find_spec("ms2_execute")
    assert found is not None, "scripts/ms2_execute.py does not exist yet"
    return importlib.import_module("ms2_execute")


def _folder(directory: Path) -> Path:
    folder = directory / "ml-1m"
    folder.mkdir()
    tables = (("ratings.dat", RATINGS), ("users.dat", USERS), ("movies.dat", MOVIES))
    for name, rows in tables:
        (folder / name).write_bytes(("\n".join(rows) + "\n").encode("latin-1"))
    return folder


def test_the_notebook_is_executed_in_a_fresh_kernel_and_saved_with_its_outputs(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    executed = _subject().execute(NOTEBOOK, _folder(tmp_path), out)
    notebook: Any = nbformat.read(executed, as_version=4)
    counts = [cell.execution_count for cell in notebook.cells if cell.cell_type == "code"]
    assert len(counts) > 5 and counts == list(range(1, len(counts) + 1)), counts
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert results["tables"]["ratings"] == [len(RATINGS), 4], results["tables"]


def test_the_kernel_talks_over_ipc_never_unencrypted_tcp(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    _subject().execute(NOTEBOOK, _folder(tmp_path), tmp_path / "out")
    printed = capfd.readouterr().err
    assert "without encryption" not in printed, printed


def test_a_folder_without_the_verified_tables_is_refused_before_any_kernel_starts(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "ml-1m"
    empty.mkdir()
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        _subject().execute(NOTEBOOK, empty, out)
    assert not out.exists(), sorted(out.iterdir())
