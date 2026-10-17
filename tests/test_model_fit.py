"""model:fit (A.100): a fit is declared in a file, run on verified data, recorded and admitted."""

from __future__ import annotations

import hashlib
from pathlib import Path

from model_run import BASELINE, FitRecord, fit_from, load, run

# Planted text is joined with chr(10): no escape sequence crosses a layer (M60).
NEWLINE = chr(10)
VERIFIED = "506d64ca44484487c11dc2d9a28de5c54948213e6b96285e298afe28d6ea4e0f"
RATINGS = [(1 + i % 3, 10 + i % 4, 1 + i % 5, 100 * (i + 1)) for i in range(10)]


def _ratings(tmp_path: Path) -> Path:
    path = tmp_path / "ratings.dat"
    rows = [f"{u}::{m}::{r}::{t}" for u, m, r, t in RATINGS]
    path.write_text(NEWLINE.join(rows) + NEWLINE, encoding="latin-1")
    return path


def _declaration(tmp_path: Path, data_sha256: str) -> Path:
    lines = [
        'contract = "model-run-declaration/v1"',
        'model = "baseline"',
        'method = "regularised user and movie biases"',
        'scaler = "none"',
        "seed = 0",
        f'data_sha256 = "{data_sha256}"',
        "[cutoffs]",
        "validation = 0.8",
        "test = 0.9",
        "[hyperparameters]",
        "shrink_user = 10.0",
        "shrink_movie = 25.0",
        "[[features]]",
        'name = "user"',
        "point_in_time = true",
        "[[features]]",
        'name = "movie"',
        "point_in_time = true",
    ]
    path = tmp_path / "declaration.toml"
    path.write_text(NEWLINE.join(lines) + NEWLINE, encoding="utf-8")
    return path


def test_the_baseline_declaration_loads_pinned_to_the_verified_data() -> None:
    declaration = load(BASELINE)
    assert declaration.data_sha256 == VERIFIED
    assert all(feature.point_in_time for feature in declaration.features)
    assert declaration.cutoffs.validation < declaration.cutoffs.test


def test_a_run_on_the_declared_data_writes_its_record_and_is_admitted(tmp_path: Path) -> None:
    ratings = _ratings(tmp_path)
    digest = hashlib.sha256(ratings.read_bytes()).hexdigest()
    out = tmp_path / "out"
    record, refusals = run(_declaration(tmp_path, digest), ratings, out, head="0" * 40)
    assert refusals == []
    written = FitRecord.model_validate_json((out / "baseline.record.json").read_text("utf-8"))
    assert written == record
    artifact = (out / "baseline.json").read_bytes()
    assert hashlib.sha256(artifact).hexdigest() == record.artifact_sha256


def test_a_run_on_data_other_than_declared_is_refused(tmp_path: Path) -> None:
    ratings = _ratings(tmp_path)
    out = tmp_path / "out"
    _, refusals = run(_declaration(tmp_path, "0" * 64), ratings, out, head="0" * 40)
    assert "ERR_MODEL_DATA_UNDECLARED" in refusals


def test_a_fit_from_a_tree_with_uncommitted_changes_is_refused(tmp_path: Path) -> None:
    ratings = _ratings(tmp_path)
    digest = hashlib.sha256(ratings.read_bytes()).hexdigest()
    out = tmp_path / "out"
    declaration = _declaration(tmp_path, digest)
    record, refusals = fit_from(declaration, ratings, out, head="0" * 40, clean=False)
    assert record is None
    assert refusals == ["ERR_MODEL_TREE_DIRTY"]
    assert not out.exists()
