# tests/test_experiment_tracking.py
"""Offline experiment runs are tracked in a local MLflow SQLite store (A.295).

Each fit runs under MLflow's scikit-learn autologging, so its parameters, metrics and model
are logged by MLflow, not by hand, into a SQLite store under the run's evidence root, with no
server and never the deprecated file store. The evidence record stays the source of truth:
its run id is the MLflow run, and each metric names the MLflow logged model it measured.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

import mlflow
import numpy as np
import pytest
from sklearn.linear_model import Ridge

from evaluation_evidence import DataSnapshot, EvaluationEvidence, Metric

TEST = "c" * 64


def _subject() -> ModuleType:
    found = importlib.util.find_spec("experiment_tracking")
    assert found is not None, "scripts/experiment_tracking.py does not exist"
    return importlib.import_module("experiment_tracking")


def _draft() -> EvaluationEvidence:
    snapshot = DataSnapshot(archive_sha256="a" * 64, train_sha256="b" * 64, test_sha256=TEST)
    rmse = Metric(
        name="rmse", value=0.9, low=0.88, high=0.92, model_id="draft", dataset_digest=TEST
    )
    return EvaluationEvidence(
        run_id="draft",
        data_snapshot=snapshot,
        protocol_digest="d" * 64,
        seeds=(7,),
        code_commit="e" * 40,
        environment_lock="f" * 64,
        tuning_budget=20,
        metrics=(rmse,),
    )


def _data() -> tuple[np.ndarray, np.ndarray]:
    features = np.arange(40.0).reshape(20, 2)
    return features, features @ np.array([0.5, -0.25]) + 1.0


def test_every_evidence_record_names_its_mlflow_run_and_model(tmp_path: Path) -> None:
    subject = _subject()
    features, ratings = _data()
    tracked = subject.track(tmp_path, Ridge(alpha=1.0), features, ratings, _draft())
    client = mlflow.MlflowClient(tracking_uri=subject.store_uri(tmp_path))
    run = client.get_run(tracked.run_id)
    assert run.data.params["alpha"] == "1.0", run.data.params
    for metric in tracked.metrics:
        model = client.get_logged_model(metric.model_id)
        assert model.source_run_id == tracked.run_id, model
    assert tracked.data_snapshot == _draft().data_snapshot, tracked


def test_mlflow_tracking_writes_only_to_a_local_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = _subject()
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:9/never-reached")
    root = tmp_path / "evidence"
    assert subject.store_uri(root) == f"sqlite:///{root / 'mlflow.db'}"
    features, ratings = _data()
    tracked = subject.track(root, Ridge(alpha=1.0), features, ratings, _draft())
    assert (root / "mlflow.db").is_file(), sorted(root.iterdir())
    assert list(elsewhere.iterdir()) == [], sorted(elsewhere.iterdir())
    assert (root / "artifacts").is_dir(), sorted(root.iterdir())
    client = mlflow.MlflowClient(tracking_uri=subject.store_uri(root))
    assert client.get_run(tracked.run_id).info.status == "FINISHED"
