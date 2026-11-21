# tests/test_bitemporal.py
"""Every rating carries two times, its event time and its observation time (A.300).

MovieLens 1M records only when a user rated a movie. A time-ordered replay therefore declares
when the system learned of each rating, as a lag after the event, and a feature built from a
rating observed at or after the prediction time is refused even when its event came earlier.
"""

from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType

import pytest

from wrangling import LeakageError, Rating


def _subject() -> ModuleType:
    found = importlib.util.find_spec("bitemporal")
    assert found is not None, "scripts/bitemporal.py does not exist"
    return importlib.import_module("bitemporal")


def test_every_rating_carries_its_event_and_observation_time() -> None:
    subject = _subject()
    ratings = (
        Rating(user_id=1, movie_id=10, rating=4, timestamp=100),
        Rating(user_id=2, movie_id=10, rating=3, timestamp=200),
    )
    observed = subject.observe(ratings, subject.ReplayAssumption(lag_seconds=60))
    assert [each.event_time for each in observed] == [100, 200], observed
    assert [each.observation_time for each in observed] == [160, 260], observed
    assert [each.rating for each in observed] == list(ratings), observed


def test_a_feature_from_a_rating_observed_after_the_prediction_is_refused() -> None:
    subject = _subject()
    earlier = Rating(user_id=1, movie_id=10, rating=4, timestamp=100)
    late = subject.observe((earlier,), subject.ReplayAssumption(lag_seconds=60))
    with pytest.raises(LeakageError, match="observed"):
        subject.audit_observed(late, prediction_time=130)
    prompt = subject.observe((earlier,), subject.ReplayAssumption(lag_seconds=0))
    subject.audit_observed(prompt, prediction_time=130)
