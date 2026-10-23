"""A fitted model is a governed artifact (A.100): declared, observed, evidenced, judged, gated."""

from __future__ import annotations

import hashlib
from pathlib import Path

import spine
from model_run import (
    ENTRYPOINT,
    POLICY,
    SUBJECT,
    Cutoffs,
    Declaration,
    Feature,
    FitRecord,
    admit,
    fit,
)

RATINGS = [
    (1, 10, 4, 100),
    (2, 10, 5, 200),
    (1, 11, 3, 300),
    (3, 11, 2, 400),
    (2, 12, 4, 500),
    (3, 10, 5, 600),
    (1, 12, 1, 700),
    (2, 11, 3, 800),
    (3, 12, 4, 900),
    (1, 10, 5, 1000),
]
# Planted ratings are joined with chr(10): no escape sequence crosses a layer (M60).
NEWLINE = chr(10)
USER = Feature(name="user", point_in_time=True)
MOVIE = Feature(name="movie", point_in_time=True)


def _ratings(tmp_path: Path) -> Path:
    path = tmp_path / "ratings.dat"
    lines = "".join(f"{u}::{m}::{r}::{t}{NEWLINE}" for u, m, r, t in RATINGS)
    path.write_text(lines, encoding="latin-1")
    return path


def _declaration(ratings: Path, features: tuple[Feature, ...] = (USER, MOVIE)) -> Declaration:
    return Declaration(
        model="baseline",
        method="regularised user and movie biases",
        features=features,
        cutoffs=Cutoffs(validation=0.8, test=0.9),
        scaler="none",
        hyperparameters={"shrink_user": 10.0, "shrink_movie": 25.0},
        seed=0,
        data_sha256=hashlib.sha256(ratings.read_bytes()).hexdigest(),
    )


def _fitted(tmp_path: Path) -> tuple[Declaration, FitRecord, Path]:
    ratings = _ratings(tmp_path)
    declaration = _declaration(ratings)
    artifact = tmp_path / "baseline.json"
    return declaration, fit(declaration, ratings, artifact, head="0" * 40), artifact


def _refusals(record: FitRecord) -> list[str]:
    found = spine.evaluate(record, SUBJECT, POLICY, ENTRYPOINT)
    return sorted(rule.code for rule in found.rules if rule.outcome == "fail")


def test_a_fit_records_its_data_window_features_scaler_and_procedure(tmp_path: Path) -> None:
    declaration, record, artifact = _fitted(tmp_path)
    assert record.data_sha256 == declaration.data_sha256
    assert (record.first_row, record.last_row) == (0, 7)
    assert record.last_training_time == 800
    assert record.validation_cutoff_time == 900
    assert record.features == declaration.features
    assert (record.method, record.scaler) == (declaration.method, declaration.scaler)
    assert record.artifact_sha256 == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert _refusals(record) == []


def test_a_fit_reading_rows_at_or_after_the_validation_cutoff_is_refused(
    tmp_path: Path,
) -> None:
    _, record, _ = _fitted(tmp_path)
    late = record.model_copy(update={"last_training_time": record.validation_cutoff_time})
    assert "ERR_MODEL_FIT_PAST_CUTOFF" in _refusals(late)


def test_a_fit_with_an_undeclared_or_non_point_in_time_feature_is_refused(
    tmp_path: Path,
) -> None:
    _, record, _ = _fitted(tmp_path)
    extra = Feature(name="later_ratings", point_in_time=True)
    undeclared = record.model_copy(update={"features": (*record.features, extra)})
    assert "ERR_MODEL_FEATURE_UNDECLARED" in _refusals(undeclared)
    leaky = Feature(name="user", point_in_time=False)
    declared = record.declared.model_copy(update={"features": (leaky, MOVIE)})
    future = record.model_copy(update={"declared": declared, "features": (leaky, MOVIE)})
    assert "ERR_MODEL_FEATURE_NOT_POINT_IN_TIME" in _refusals(future)


def test_a_fit_whose_data_fingerprint_differs_from_the_declared_one_is_refused(
    tmp_path: Path,
) -> None:
    _, record, _ = _fitted(tmp_path)
    other = record.model_copy(update={"data_sha256": "0" * 64})
    assert "ERR_MODEL_DATA_UNDECLARED" in _refusals(other)


def test_scoring_refuses_a_model_without_a_passing_verdict_bound_to_its_digest(
    tmp_path: Path,
) -> None:
    _, record, artifact = _fitted(tmp_path)
    assert admit(record, artifact) == []
    late = record.model_copy(update={"last_training_time": record.validation_cutoff_time})
    assert "ERR_MODEL_FIT_PAST_CUTOFF" in admit(late, artifact)
    artifact.write_bytes(artifact.read_bytes() + b" ")
    assert "ERR_MODEL_ARTIFACT_UNBOUND" in admit(record, artifact)


def test_an_absent_record_is_refused_by_the_policy(tmp_path: Path) -> None:
    _, record, _ = _fitted(tmp_path)
    found = spine.evaluate(record, "absent", POLICY, ENTRYPOINT)
    refused = {rule.code for rule in found.rules if rule.outcome == "fail"}
    assert "ERR_MODEL_INPUT_MISSING" in refused
