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

__all__ = [
    "GateFeatures",
    "LeakageError",
    "bucket_report",
    "fit_gate",
    "fitted_weights",
    "gate_features",
    "gate_weights",
    "mix",
]


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


def _inputs(feature: GateFeatures) -> tuple[float, float, float]:
    """The fitted gate's inputs: an intercept and the two counts as log(1 + n)."""
    return (1.0, math.log1p(feature.user_count), math.log1p(feature.movie_count))


def fitted_weights(theta: Sequence[Sequence[float]], feature: GateFeatures) -> tuple[float, ...]:
    """The fitted gate's weights for one rating: a softmax of one linear score per expert."""
    x = _inputs(feature)
    scores = [math.fsum(t * v for t, v in zip(row, x, strict=True)) for row in theta]
    return gate_weights(scores)


def fit_gate(
    features: Sequence[GateFeatures],
    predictions: Sequence[Sequence[float]],
    targets: Sequence[float],
    *,
    rate: float = 0.5,
    steps: int = 400,
) -> tuple[tuple[tuple[float, ...], ...], tuple[float, ...]]:
    """The gate fitted by gradient descent on the mixture's squared error (A.360).

    The experts are held fixed. From the uniform gate (every score zero), each step moves expert
    j's scores by the mean over ratings of 2 (mix - y) w_j (p_j - mix) times the inputs, the same
    descent as site/src/mechanisms/lib/moefit.js, so the page and the model fit the same gate.
    """
    if not features:
        raise ValueError("a gate is fitted on at least one rating")
    experts = len(predictions[0])
    theta = [[0.0, 0.0, 0.0] for _ in range(experts)]
    inputs = [_inputs(feature) for feature in features]
    rows = list(zip(features, inputs, predictions, targets, strict=True))
    losses: list[float] = []
    for step in range(steps + 1):
        gradient = [[0.0, 0.0, 0.0] for _ in range(experts)]
        loss = 0.0
        for feature, x, prediction, target in rows:
            weights = fitted_weights(theta, feature)
            mixed = mix(prediction, weights)
            error = mixed - target
            loss += error * error
            for j, weight in enumerate(weights):
                slope = 2.0 * error * weight * (prediction[j] - mixed)
                for d, value in enumerate(x):
                    gradient[j][d] += slope * value
        losses.append(loss / len(rows))
        if step == steps:
            break
        for j in range(experts):
            for d in range(3):
                theta[j][d] -= rate * gradient[j][d] / len(rows)
    return tuple(tuple(row) for row in theta), tuple(losses)
