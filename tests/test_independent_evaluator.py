# tests/test_independent_evaluator.py
"""The evaluator is separate from every model (A.291).

The offline harness alone holds the split, the held-out ratings and the metric code. A model
receives only the user, movie and time of each rating it must predict, and returns predictions;
a model's own account of its accuracy is never read.
"""

from __future__ import annotations

import importlib
import importlib.util
import math
from types import ModuleType

import pytest

from nonvacuous import nonempty


def _subject() -> ModuleType:
    found = importlib.util.find_spec("independent_evaluator")
    assert found is not None, "scripts/independent_evaluator.py does not exist"
    return importlib.import_module("independent_evaluator")


class _Spy:
    """A model that records every query it is given and predicts 3.0 for each."""

    def __init__(self) -> None:
        self.seen: list[object] = []

    def predict(self, queries: tuple[object, ...]) -> tuple[float, ...]:
        self.seen.extend(queries)
        return tuple(3.0 for _ in queries)


class _Boastful(_Spy):
    """A model that reports a perfect score of its own, which the evaluator must ignore."""

    rmse = 0.0
    mae = 0.0


class _Short(_Spy):
    """A model that answers fewer queries than it was asked."""

    def predict(self, queries: tuple[object, ...]) -> tuple[float, ...]:
        return (3.0,)


def _held_out(subject: ModuleType) -> tuple[object, ...]:
    return (
        subject.Observation(user=1, movie=10, time=100, rating=4),
        subject.Observation(user=2, movie=20, time=101, rating=2),
    )


def test_a_model_never_receives_a_held_out_rating() -> None:
    subject = _subject()
    spy = _Spy()
    subject.evaluate(spy, _held_out(subject))
    assert len(spy.seen) == 2, spy.seen
    for query in nonempty(spy.seen):
        assert isinstance(query, subject.Query), type(query)
        assert set(type(query).model_fields) == {"user", "movie", "time"}, query
        assert not hasattr(query, "rating"), query


def test_metrics_are_computed_only_by_the_evaluator() -> None:
    subject = _subject()
    result = subject.evaluate(_Boastful(), _held_out(subject))
    assert result.count == 2, result
    assert result.rmse == pytest.approx(math.sqrt(((3.0 - 4) ** 2 + (3.0 - 2) ** 2) / 2)), result
    assert result.mae == pytest.approx(1.0), result
    with pytest.raises(subject.EvaluatorError, match="2"):
        subject.evaluate(_Short(), _held_out(subject))
