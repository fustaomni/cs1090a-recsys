# scripts/independent_evaluator.py
"""The offline evaluator, separate from every model (A.291).

A recommender is evaluated as a treatment: the harness alone holds the held-out ratings and
the metric code. A model is asked only who rated which movie and when, and it answers with
predictions; anything it says about its own accuracy is never read. The split that produces
the held-out ratings is A.284's, applied by the caller before anything reaches this module.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

from pydantic import Field

from contract_base import Contract


class Query(Contract):
    """What a model is asked: the user, the movie and the time, never the rating."""

    user: int = Field(ge=1)
    movie: int = Field(ge=1)
    time: int = Field(ge=0)


class Observation(Contract):
    """A held-out rating, which only the evaluator holds."""

    user: int = Field(ge=1)
    movie: int = Field(ge=1)
    time: int = Field(ge=0)
    rating: int = Field(ge=1, le=5)


class EvaluationResult(Contract):
    """What the evaluator measured, from the model's predictions and its own held-out ratings."""

    count: int = Field(ge=1)
    rmse: float = Field(ge=0)
    mae: float = Field(ge=0)


class EvaluatorError(ValueError):
    """An answer the evaluator cannot score, refused by name rather than scored."""


class Model(Protocol):
    """Anything that predicts a rating for each query it is given."""

    def predict(self, queries: tuple[Query, ...]) -> Sequence[float]: ...


def evaluate(model: Model, held_out: Sequence[Observation]) -> EvaluationResult:
    """Ask the model only for queries, then score its answers against the held-out ratings."""
    if not held_out:
        raise EvaluatorError("there is no held-out rating to evaluate")
    queries = tuple(Query(user=each.user, movie=each.movie, time=each.time) for each in held_out)
    predictions = tuple(float(value) for value in model.predict(queries))
    if len(predictions) != len(held_out):
        raise EvaluatorError(f"the model answered {len(predictions)} of {len(held_out)} queries")
    errors = [guess - each.rating for guess, each in zip(predictions, held_out, strict=True)]
    if not all(math.isfinite(error) for error in errors):
        raise EvaluatorError("the model returned a prediction that is not a finite number")
    count = len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / count)
    mae = sum(abs(error) for error in errors) / count
    return EvaluationResult(count=count, rmse=rmse, mae=mae)
