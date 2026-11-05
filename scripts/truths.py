# scripts/truths.py
"""The three kinds of truth kept apart: requirement, observation and verdict (A.241).

A requirement changes only by a reviewed commit, so only the plan writers and source:apply may
write one. An observation records what happened and carries no judgement of it. A verdict names
the policy and the evidence it judged, so it can be judged again offline from those alone.
"""

from __future__ import annotations

import tomllib
from fnmatch import fnmatch
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from contract_base import Contract, from_document
from plan_models import PlanStatus
from spine import Verdict, digest, policy_revision

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "contracts" / "truths.toml"
REQUIREMENT_WRITE = "TRUTH_REQUIREMENT_WRITE"


class Truths(Contract):
    """truths/v1: requirements and their writers, observations, and forbidden fields."""

    contract: Literal["truths/v1"]
    requirements: tuple[str, ...]
    requirement_writers: tuple[str, ...]
    observations: tuple[str, ...]
    verdict_fields: tuple[str, ...]


def register(path: Path = REGISTER) -> Truths:
    """The register, validated as truths/v1."""
    return from_document(Truths, tomllib.loads(path.read_text(encoding="utf-8")))


def refuse_write(task: str, path: str, truths: Truths) -> str | None:
    """The problem code refusing TASK's write of PATH, or None when it may write it."""
    if task in truths.requirement_writers:
        return None
    if any(fnmatch(path, pattern) for pattern in truths.requirements):
        return REQUIREMENT_WRITE
    return None


def audit_observations(classes: list[type[BaseModel]], truths: Truths) -> tuple[str, ...]:
    """Each declared observation class carrying a verdict field, as class.field."""
    found = [
        f"{name}.{field}"
        for model in classes
        if (name := f"{model.__module__}.{model.__qualname__}") in truths.observations
        for field in model.model_fields
        if field in truths.verdict_fields
    ]
    return tuple(sorted(found))


def recompute(verdict: Verdict, policy_dir: Path, evidence: BaseModel) -> bool:
    """Whether VERDICT's policy and evidence digests reproduce from the pinned inputs alone."""
    reproduced = verdict.policy_revision == policy_revision(policy_dir)
    return reproduced and verdict.evidence_digest == digest(evidence)


def completed(step: str, status: object) -> bool:
    """Whether STEP is done, read only from the plan policy's decided status."""
    if not isinstance(status, PlanStatus):
        raise TypeError(f"completion is read from plan-status/v1, not {type(status).__name__}")
    return status.steps[step].state == "done"
