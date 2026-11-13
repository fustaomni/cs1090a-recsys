# tests/test_ms2_notebook.py
"""The Milestone 2 notebook runs top to bottom in a fresh kernel and reports the brief (A.225).

It is executed as 2026 practice trusts a notebook: in batch, in a fresh kernel, by nbclient, on
an archive and tables this test writes, its paths given only through the environment. Its order,
its results, its quality rules, its findings and decisions and its figures are read back.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import nbformat
import pytest
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "milestone2.ipynb"
SECTIONS = (
    "Canvas project group",
    "Getting the data",
    "Understanding the data",
    "Cleaning and preprocessing",
    "Project question",
)
CHECKS = (
    "Missing data",
    "Unusual values",
    "Class balance",
    "Scale of the features",
    "Information leakage",
)
FIELDS = (
    "size_megabytes",
    "tables",
    "summaries",
    "missing_by_column",
    "missing_by_gender",
    "unusual_users",
    "rating_balance",
    "quality",
    "split",
    "leakage_refused",
    "figures",
)
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


def _data(directory: Path, ratings: tuple[str, ...] = RATINGS) -> Path:
    folder = directory / "ml-1m"
    folder.mkdir()
    tables = (("ratings.dat", ratings), ("users.dat", USERS), ("movies.dat", MOVIES))
    for name, rows in tables:
        (folder / name).write_bytes(("\n".join(rows) + "\n").encode("latin-1"))
    with zipfile.ZipFile(directory / "ml-1m.zip", "w") as bundle:
        for path in sorted(folder.iterdir()):
            bundle.write(path, f"ml-1m/{path.name}")
    return directory


def _run(directory: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, dict[str, Any]]:
    assert NOTEBOOK.is_file(), "notebooks/milestone2.ipynb does not exist yet"
    results = directory / "results.json"
    monkeypatch.setenv("MS2_DATA", str(directory / "ml-1m"))
    monkeypatch.setenv("MS2_ARCHIVE", str(directory / "ml-1m.zip"))
    monkeypatch.setenv("MS2_RESULTS", str(results))
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    where = {"metadata": {"path": str(NOTEBOOK.parent)}}
    NotebookClient(notebook, kernel_name="python3", timeout=180, resources=where).execute()
    found: dict[str, Any] = json.loads(results.read_text(encoding="utf-8"))
    return notebook, found


def _printed(notebook: Any) -> str:
    texts = [
        str(output.get("text", ""))
        for cell in notebook.cells
        if cell.cell_type == "code"
        for output in cell.outputs
    ]
    return "".join(texts)


def test_every_section_the_milestone_requires_is_present_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook, _ = _run(_data(tmp_path), monkeypatch)
    headings = [
        cell.source.splitlines()[0]
        for cell in notebook.cells
        if cell.cell_type == "markdown" and cell.source.startswith("#")
    ]
    positions = [next((i for i, h in enumerate(headings) if s in h), -1) for s in SECTIONS]
    assert -1 not in positions and positions == sorted(positions), headings
    assert "34" in notebook.cells[0].source, notebook.cells[0].source


def test_every_number_the_milestone_requires_is_a_results_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, results = _run(_data(tmp_path), monkeypatch)
    assert set(FIELDS) <= set(results), sorted(results)
    assert results["tables"]["ratings"] == [len(RATINGS), 4], results["tables"]
    assert results["tables"]["users"] == [len(USERS), 5], results["tables"]
    assert results["size_megabytes"] > 0, results["size_megabytes"]


def test_each_quality_rule_reports_pass_fail_or_unknown_with_its_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, results = _run(_data(tmp_path), monkeypatch)
    rules = results["quality"]
    assert len(rules) == 5, rules
    assert all(rule["status"] in {"pass", "fail", "unknown"} for rule in rules), rules
    assert all(isinstance(rule["count"], int) for rule in rules), rules


def test_a_rating_outside_one_to_five_or_an_orphan_user_fails_its_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = (*RATINGS, "1::1357::6::978302200", "99::1193::4::978302300")
    _, results = _run(_data(tmp_path, rows), monkeypatch)
    named = {rule["name"]: (rule["status"], rule["count"]) for rule in results["quality"]}
    assert named["rating-in-range"] == ("fail", 1), named
    assert named["rating-user-exists"] == ("fail", 1), named


def test_a_feature_computed_from_a_later_rating_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, results = _run(_data(tmp_path), monkeypatch)
    assert results["leakage_refused"] is True, results
    split = results["split"]
    assert split["train_latest"] < split["cutoff"] <= split["test_earliest"], split
    assert split["train"] + split["test"] == len(RATINGS), split


def test_the_notebook_is_an_ipynb_that_runs_top_to_bottom_in_a_fresh_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook, _ = _run(_data(tmp_path), monkeypatch)
    assert NOTEBOOK.suffix == ".ipynb"
    nbformat.validate(notebook)
    counts = [cell.execution_count for cell in notebook.cells if cell.cell_type == "code"]
    assert counts == list(range(1, len(counts) + 1)), counts


def test_each_check_the_brief_lists_reports_its_finding_and_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook, _ = _run(_data(tmp_path), monkeypatch)
    printed = _printed(notebook)
    written = [cell.source for cell in notebook.cells if cell.cell_type == "markdown"]
    for check in CHECKS:
        assert f"{check} finding:" in printed, (check, printed)
        assert any(check in text and "Decision:" in text for text in written), check


def test_every_plot_has_a_title_and_labelled_axes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, results = _run(_data(tmp_path), monkeypatch)
    figures = results["figures"]
    assert figures, results
    for figure in figures:
        assert figure["title"] and figure["xlabel"] and figure["ylabel"], figure
