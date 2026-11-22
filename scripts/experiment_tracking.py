# scripts/experiment_tracking.py
"""Offline experiment runs are tracked in a local MLflow SQLite store (A.295).

A fit runs under MLflow's scikit-learn autologging, so its parameters, metrics and model are
logged by MLflow and never by hand. The store is a SQLite file under the run's evidence root,
and the experiment's artifacts live beside it: no server, never the deprecated file store,
never the working directory, whatever MLFLOW_TRACKING_URI says. The evidence record stays the
source of truth and MLflow the index: its run id becomes the MLflow run, and each metric names
the MLflow logged model it measured.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

import mlflow

from evaluation_evidence import EvaluationEvidence

EXPERIMENT = "offline"


class Estimator(Protocol):
    """A scikit-learn estimator: autologging records whatever fit receives."""

    def fit(self, features: Any, ratings: Any) -> Any: ...


class TrackingError(RuntimeError):
    """MLflow recorded no logged model for the fit, so the record cannot name one."""


def store_uri(root: Path) -> str:
    """The SQLite store under the evidence root."""
    return f"sqlite:///{root / 'mlflow.db'}"


@contextmanager
def _local_store(root: Path) -> Iterator[str]:
    """Point MLflow at the root's store for the fit, then restore what was set before."""
    root.mkdir(parents=True, exist_ok=True)
    previous = mlflow.get_tracking_uri()
    mlflow.set_tracking_uri(store_uri(root))
    try:
        found = mlflow.get_experiment_by_name(EXPERIMENT)
        if found is None:
            artifacts = (root / "artifacts").as_uri()
            yield mlflow.create_experiment(EXPERIMENT, artifact_location=artifacts)
        else:
            yield found.experiment_id
    finally:
        mlflow.set_tracking_uri(previous)


def track(
    root: Path,
    estimator: Estimator,
    features: Any,
    ratings: Any,
    draft: EvaluationEvidence,
) -> EvaluationEvidence:
    """Fit under autologging and return the record naming its MLflow run and logged model."""
    with _local_store(root) as experiment:
        mlflow.sklearn.autolog(log_models=True, silent=True)
        try:
            with mlflow.start_run(experiment_id=experiment) as run:
                estimator.fit(features, ratings)
            model = mlflow.last_logged_model()
        finally:
            mlflow.sklearn.autolog(disable=True)
    if model is None:
        raise TrackingError(f"run {run.info.run_id} logged no model")
    named = tuple(each.model_copy(update={"model_id": model.model_id}) for each in draft.metrics)
    return draft.model_copy(update={"run_id": run.info.run_id, "metrics": named})
