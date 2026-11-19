# scripts/moe.py
"""A gated mixture of experts predicts each rating (A.345).

Each expert predicts a rating; a softmax gate turns one logit per expert into weights that are
non-negative and sum to one, the largest logit subtracted first so an extreme logit cannot
overflow; the prediction is the weighted sum. The gate's features read only the training window,
and each cold-start bucket reports the mixture's RMSE beside the bias baseline's.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from wrangling import LeakageError, Rating

__all__ = ["GateFeatures", "LeakageError", "bucket_report", "gate_features", "gate_weights", "mix"]


def gate_weights(logits: Sequence[float]) -> tuple[float, ...]:
    """A numerically stable softmax: each weight is non-negative and together they sum to one."""
    if not logits:
        raise ValueError("a gate needs at least one expert")
    top = max(logits)
    raised = [math.exp(logit - top) for logit in logits]
    total = math.fsum(raised)
    return tuple(value / total for value in raised)


def mix(predictions: Sequence[float], weights: Sequence[float]) -> float:
    """The experts' predictions combined by the gate's weights."""
    if len(predictions) != len(weights):
        raise ValueError(f"{len(predictions)} predictions for {len(weights)} weights")
    return math.fsum(p * w for p, w in zip(predictions, weights, strict=True))


@dataclass(frozen=True)
class GateFeatures:
    """What the gate reads for one rating: its user's and its movie's training-window history."""

    user_count: int
    movie_count: int


def gate_features(training: tuple[Rating, ...], target: Rating, boundary: int) -> GateFeatures:
    """The gate's features from the training window only; a rating at or past it is refused."""
    late = [r for r in training if r.timestamp >= boundary]
    if late:
        raise LeakageError(f"{len(late)} training rating(s) at or after the boundary {boundary}")
    users = sum(r.user_id == target.user_id for r in training)
    movies = sum(r.movie_id == target.movie_id for r in training)
    return GateFeatures(user_count=users, movie_count=movies)


def bucket_report(rows: Sequence[tuple[str, float, float, float]]) -> dict[str, dict[str, float]]:
    """Each bucket's RMSE for the mixture and the baseline, from (bucket, mixture, baseline, y)."""
    errors: dict[str, list[tuple[float, float]]] = {}
    for bucket, mixture, baseline, actual in rows:
        errors.setdefault(bucket, []).append(((mixture - actual) ** 2, (baseline - actual) ** 2))
    return {
        bucket: {
            "rmse": math.sqrt(sum(m for m, _ in found) / len(found)),
            "baseline_rmse": math.sqrt(sum(b for _, b in found) / len(found)),
        }
        for bucket, found in errors.items()
    }
