# scripts/statistical_evaluation.py
"""Comparison evidence from paired per-user losses, and never a decision (A.303).

A recommender's ratings cluster by user, so the unit of resampling is the user: each user's
paired losses become one mean difference, the bootstrap resamples those users with replacement,
and the pre-declared test flips the sign of each user's difference. A user who rated more moves
neither. The exploratory comparisons are Holm adjusted, and the test window is read exactly
once. What comes out is A.302's ComparisonEvidence; the verdict is the gate's, never this code's.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator, Mapping, Sequence

from pydantic import Field

from contract_base import Contract
from evaluation_contracts import ComparisonEvidence, IntervalMethod
from independent_evaluator import Observation


class PairedLoss(Contract):
    """One held-out rating's loss under the model and under the baseline, by user."""

    user: int = Field(ge=1)
    model_loss: float = Field(ge=0)
    baseline_loss: float = Field(ge=0)


class StatisticsError(ValueError):
    """Losses the statistics cannot compare, refused by name rather than estimated."""


class TestWindowSpentError(RuntimeError):
    """The test window was already evaluated; it is read exactly once."""


def user_differences(rows: Sequence[PairedLoss]) -> tuple[float, ...]:
    """Each user's mean baseline loss less mean model loss, in user order; positive is better."""
    by_user: dict[int, list[float]] = {}
    for row in rows:
        by_user.setdefault(row.user, []).append(row.baseline_loss - row.model_loss)
    if len(by_user) < 2:
        raise StatisticsError(f"{len(by_user)} user(s): a user-level comparison needs two")
    return tuple(sum(diffs) / len(diffs) for _, diffs in sorted(by_user.items()))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _quantile(ordered: Sequence[float], q: float) -> float:
    position = q * (len(ordered) - 1)
    below = math.floor(position)
    above = math.ceil(position)
    weight = position - below
    return ordered[below] * (1 - weight) + ordered[above] * weight


def _stream(seed: int, label: str) -> Iterator[int]:
    """Seeded 64-bit draws from SHA-256 in counter mode: the same seed gives the same draws."""
    counter = 0
    while True:
        block = hashlib.sha256(f"{seed}:{label}:{counter}".encode()).digest()
        for offset in range(0, len(block), 8):
            yield int.from_bytes(block[offset : offset + 8], "big")
        counter += 1


def user_bootstrap(
    differences: Sequence[float], *, resamples: int, seed: int, alpha: float
) -> tuple[float, float]:
    """A percentile interval for the mean difference, resampling users with replacement."""
    draws = _stream(seed, "user-bootstrap")
    count = len(differences)
    means = sorted(
        _mean([differences[next(draws) % count] for _ in range(count)]) for _ in range(resamples)
    )
    return _quantile(means, alpha / 2), _quantile(means, 1 - alpha / 2)


def sign_flip_p(differences: Sequence[float], *, resamples: int, seed: int) -> float:
    """The two-sided user-level sign-flip permutation p-value of the mean difference."""
    draws = _stream(seed, "sign-flip")
    observed = abs(_mean(differences))
    extreme = sum(
        abs(_mean([value if next(draws) & 1 else -value for value in differences])) >= observed
        for _ in range(resamples)
    )
    return (extreme + 1) / (resamples + 1)


def compare(
    model_id: str,
    baseline_id: str,
    rows: Sequence[PairedLoss],
    *,
    resamples: int,
    seed: int,
    alpha: float,
) -> ComparisonEvidence:
    """The paired comparison as evidence: estimate, user-bootstrap interval and sign-flip test."""
    differences = user_differences(rows)
    low, high = user_bootstrap(differences, resamples=resamples, seed=seed, alpha=alpha)
    return ComparisonEvidence(
        model_id=model_id,
        baseline_id=baseline_id,
        estimate=_mean(differences),
        low=low,
        high=high,
        p_value=sign_flip_p(differences, resamples=resamples, seed=seed),
        interval_method=IntervalMethod.USER_BOOTSTRAP,
    )


def holm(p_values: Mapping[str, float]) -> dict[str, float]:
    """Holm's step-down adjustment across the exploratory comparisons, each capped at one."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (count - rank) * value))
        adjusted[name] = running
    return adjusted


class TestWindow:
    """The held-out test ratings, handed out once and refused every time after."""

    __test__ = False

    def __init__(self, held_out: Sequence[Observation]) -> None:
        self._held_out = tuple(held_out)
        self._spent = False

    def open(self) -> tuple[Observation, ...]:
        if self._spent:
            raise TestWindowSpentError("the test window was already evaluated; it is read once")
        self._spent = True
        return self._held_out
