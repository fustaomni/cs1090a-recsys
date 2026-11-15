# scripts/evaluation_evidence.py
"""evaluation-evidence/v1: one offline evaluation run's evidence, as validated data (A.283).

A run's numbers are worth what can be traced: the data snapshot they were measured on, the
protocol fixed before results, every seed, the code commit, the environment lock and the tuning
budget, and each metric tied to the model and the dataset it measured, as MLflow 3 links a
metric to a logged model and a dataset.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from contract_base import Contract

SHA256 = r"^[0-9a-f]{64}$"


class DataSnapshot(Contract):
    """The bytes the run read: the archive and the two splits, each by SHA-256."""

    archive_sha256: str = Field(pattern=SHA256)
    train_sha256: str = Field(pattern=SHA256)
    test_sha256: str = Field(pattern=SHA256)


class Metric(Contract):
    """One measured value, its user-clustered interval, and what it was measured on."""

    name: str = Field(min_length=1)
    value: float
    low: float
    high: float
    model_id: str | None = None
    dataset_digest: str | None = None

    @model_validator(mode="after")
    def _contains_its_value(self) -> Self:
        if not self.low <= self.value <= self.high:
            raise ValueError(f"interval [{self.low}, {self.high}] excludes {self.value}")
        return self


class EvaluationEvidence(Contract):
    """evaluation-evidence/v1: everything one offline evaluation run's numbers rest on."""

    contract: Literal["evaluation-evidence/v1"] = "evaluation-evidence/v1"
    run_id: str = Field(min_length=1)
    data_snapshot: DataSnapshot | None = None
    protocol_digest: str = Field(pattern=SHA256)
    seeds: tuple[int, ...] = Field(min_length=1)
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    environment_lock: str = Field(pattern=SHA256)
    tuning_budget: int = Field(ge=0)
    metrics: tuple[Metric, ...] = Field(min_length=1)
