# scripts/prediction_evidence.py
"""Every offline prediction is typed, append-only evidence written at prediction time (A.296).

A PredictionRecord names what made the prediction, the model and its version, the evaluator and
MLflow runs, the dataset digest and the explanation method, and each feature's provenance: the
latest rating it was built from by event time and by observation time, both strictly before the
prediction, as A.292 bounds every feature. The outcome is never a field; it arrives later as its
own record. The log chains each line to the one before by SHA-256, so appending a prediction id
again with other content, or editing a line in place, is refused by name.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from contract_base import Contract

SHA256 = r"^[0-9a-f]{64}$"
GENESIS = "0" * 64


class FeatureProvenance(Contract):
    """One feature and the latest rating it was built from, by event and observation time."""

    name: str = Field(min_length=1)
    event_cutoff: int = Field(ge=0)
    observation_cutoff: int = Field(ge=0)


class PredictionRecord(Contract):
    """What one prediction was made from, and never its outcome."""

    prediction_id: str = Field(min_length=1)
    predicted_at: int = Field(ge=0)
    predicted_rating: float
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    evaluator_run: str = Field(min_length=1)
    mlflow_run: str = Field(min_length=1)
    dataset_digest: str = Field(pattern=SHA256)
    explanation_method: str = Field(min_length=1)
    explanation_version: str = Field(min_length=1)
    features: tuple[FeatureProvenance, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _features_precede_the_prediction(self) -> Self:
        late = [
            each.name
            for each in self.features
            if max(each.event_cutoff, each.observation_cutoff) >= self.predicted_at
        ]
        if late:
            raise ValueError(f"features known at or after the prediction: {', '.join(late)}")
        return self


class _Entry(Contract):
    """One line of the log: the record, the line before's digest and this line's digest."""

    record: PredictionRecord
    previous: str = Field(pattern=SHA256)
    digest: str = Field(pattern=SHA256)


class RewrittenRecordError(ValueError):
    """A prediction appended again with other content, or a log line changed in place."""


def _canonical(record: PredictionRecord) -> str:
    return json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _chained(previous: str, record: PredictionRecord) -> str:
    return hashlib.sha256(f"{previous}\n{_canonical(record)}".encode()).hexdigest()


class PredictionLog:
    """An append-only JSON Lines log of prediction records, each chained to the one before."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _entries(self) -> list[_Entry]:
        if not self.path.exists():
            return []
        entries: list[_Entry] = []
        previous = GENESIS
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            entry = _Entry.model_validate_json(line)
            if entry.previous != previous or entry.digest != _chained(previous, entry.record):
                raise RewrittenRecordError(f"line {number} of {self.path} was changed in place")
            entries.append(entry)
            previous = entry.digest
        return entries

    def read(self) -> tuple[PredictionRecord, ...]:
        """Every record, in order, once the whole chain is proven unchanged."""
        return tuple(entry.record for entry in self._entries())

    def append(self, record: PredictionRecord) -> None:
        """Append one record; the same prediction id with other content is refused."""
        entries = self._entries()
        for entry in entries:
            if entry.record.prediction_id != record.prediction_id:
                continue
            if _canonical(entry.record) == _canonical(record):
                return
            raise RewrittenRecordError(f"{record.prediction_id} is recorded with other content")
        previous = entries[-1].digest if entries else GENESIS
        entry = _Entry(record=record, previous=previous, digest=_chained(previous, record))
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(entry.model_dump_json() + "\n")
