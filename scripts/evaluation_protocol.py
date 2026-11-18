# scripts/evaluation_protocol.py
"""Every offline evaluation follows one research policy fixed before any result (A.284).

contracts/evaluation-protocol.toml is that policy, validated here as evaluation-protocol/v1.
The SHA-256 of its bytes is the digest every evaluation-evidence/v1 record must name, so a
record made under any other policy is refused before it is used. The split audit refuses a
training rating dated at or after the test boundary, and counts the users and movies it leaves
cold.
"""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from contract_base import Contract, from_document
from evaluation_evidence import EvaluationEvidence
from wrangling import Rating


class Split(Contract):
    """The declared split: its protocol and the two quantile cuts, validation before test."""

    protocol: str = Field(min_length=1)
    validation_quantile: float = Field(gt=0, lt=1)
    test_quantile: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def _validation_first(self) -> Self:
        if not self.validation_quantile < self.test_quantile:
            raise ValueError("the validation cut must come before the test cut")
        return self


class EvaluationProtocol(Contract):
    """evaluation-protocol/v1: the research policy, declared before any result."""

    contract: Literal["evaluation-protocol/v1"] = "evaluation-protocol/v1"
    hypotheses: tuple[str, ...] = Field(min_length=1)
    baselines: tuple[str, ...] = Field(min_length=1)
    metrics: tuple[str, ...] = Field(min_length=1)
    tuning_budget: int = Field(ge=0)
    primary_test: str = Field(min_length=1)
    practical_threshold: str = Field(min_length=1)
    split: Split


class UndeclaredProtocolError(ValueError):
    """An evidence record names a protocol digest other than the declared one."""


class LeakingSplitError(ValueError):
    """A training rating is dated at or after the test boundary."""


@dataclass(frozen=True)
class SplitAudit:
    """The users and movies the test window holds that training never saw."""

    cold_users: int
    cold_movies: int


def load(path: Path) -> EvaluationProtocol:
    """The declared protocol, validated."""
    return from_document(EvaluationProtocol, tomllib.loads(path.read_text(encoding="utf-8")))


def digest(path: Path) -> str:
    """The protocol's identity: the SHA-256 of its file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def admit(evidence: EvaluationEvidence, path: Path) -> EvaluationEvidence:
    """The evidence, only when it names the declared protocol's digest."""
    load(path)
    declared = digest(path)
    if evidence.protocol_digest != declared:
        raise UndeclaredProtocolError(
            f"evidence names protocol {evidence.protocol_digest}, not the declared {declared}"
        )
    return evidence


def audit_split(train: tuple[Rating, ...], test: tuple[Rating, ...], boundary: int) -> SplitAudit:
    """Refuse a training rating at or after the boundary; count what the split leaves cold."""
    late = [r for r in train if r.timestamp >= boundary]
    if late:
        raise LeakingSplitError(
            f"{len(late)} training rating(s) at or after the test boundary {boundary}"
        )
    users = {r.user_id for r in train}
    movies = {r.movie_id for r in train}
    return SplitAudit(
        cold_users=len({r.user_id for r in test} - users),
        cold_movies=len({r.movie_id for r in test} - movies),
    )
