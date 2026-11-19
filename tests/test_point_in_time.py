# tests/test_point_in_time.py
"""Every feature is point-in-time correct, stricter than an inclusive bound (A.292).

MovieLens timestamps have one-second resolution and collide, so a feature for a rating is
built only from ratings dated strictly before it: a same-second rating, the target included,
never feeds its own features, and a feature built from one is refused.
"""

from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType

import pytest

from wrangling import Rating

TARGET = Rating(1, 10, 3, 300)


def _subject() -> ModuleType:
    found = importlib.util.find_spec("point_in_time")
    assert found is not None, "scripts/point_in_time.py does not exist"
    return importlib.import_module("point_in_time")


def test_every_feature_is_built_from_ratings_strictly_before_its_target() -> None:
    subject = _subject()
    history = (
        Rating(1, 10, 2, 100),
        Rating(1, 11, 4, 200),
        Rating(2, 10, 5, 300),
        Rating(1, 12, 1, 300),
        TARGET,
    )
    built = subject.features_before(history, TARGET)
    assert (built.user_count, built.user_mean) == (2, 3.0), built
    assert (built.movie_count, built.movie_mean) == (1, 2.0), built


def test_a_feature_built_from_a_same_second_rating_is_refused() -> None:
    subject = _subject()
    with pytest.raises(subject.LeakageError, match="300"):
        subject.audit((Rating(2, 10, 5, 300),), TARGET)
    subject.audit((Rating(2, 10, 5, 299),), TARGET)
