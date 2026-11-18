# tests/test_ms2_split.py
"""Milestone 2's split is three global temporal windows, each reported as data (A.350).

Training is every rating before the validation quantile, validation runs from it to the test
cut, and test starts at the delivered 0.8 cut, so the test window shown to the TF is unchanged.
Each window reports its ratings, users, movies and time span; validation and test report their
cold-start counts against everything before them; and the leakage verdict fails when a training
or validation rating reaches past its window. Ten ratings, one per second, each its own movie.
"""

from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType
from typing import Any

VALIDATION = 0.7
TEST = 0.8


def _subject() -> ModuleType:
    found = importlib.util.find_spec("wrangling")
    assert found is not None, "scripts/wrangling.py does not exist"
    return importlib.import_module("wrangling")


def _ratings(wrangling: ModuleType) -> tuple[Any, ...]:
    """Ten ratings at seconds 0 to 9, users 1 to 3 in turn, each a movie of its own."""
    return tuple(wrangling.Rating(t % 3 + 1, 100 + t, 4, t) for t in range(10))


def test_the_windows_are_cut_at_the_declared_quantiles() -> None:
    wrangling = _subject()
    assert hasattr(wrangling, "split_three"), "wrangling has no three-way split yet"
    ratings = _ratings(wrangling)
    split = wrangling.split_three(ratings, VALIDATION, TEST)
    assert (split.validation_cutoff, split.test_cutoff) == (7, 8), split
    assert [r.timestamp for r in split.train] == list(range(7)), split.train
    assert [r.timestamp for r in split.validation] == [7], split.validation
    delivered = wrangling.split_at(ratings, wrangling.time_cutoff(ratings, TEST))
    assert split.test == delivered.test, (split.test, delivered.test)


def test_each_window_reports_its_rows_users_movies_and_span() -> None:
    wrangling = _subject()
    assert hasattr(wrangling, "split_audit"), "wrangling has no split audit yet"
    split = wrangling.split_three(_ratings(wrangling), VALIDATION, TEST)
    audit = wrangling.split_audit(split)
    train = {"ratings": 7, "users": 3, "movies": 7, "first": 0, "last": 6}
    later = {"user-unseen": 0}
    assert audit["windows"] == {
        "train": train,
        "validation": {
            **{"ratings": 1, "users": 1, "movies": 1, "first": 7, "last": 7},
            **later,
            "movie-unseen": 1,
        },
        "test": {
            **{"ratings": 2, "users": 2, "movies": 2, "first": 8, "last": 9},
            **later,
            "movie-unseen": 2,
        },
    }, audit


def test_no_training_or_validation_rating_reaches_past_its_window() -> None:
    wrangling = _subject()
    assert hasattr(wrangling, "split_audit"), "wrangling has no split audit yet"
    ratings = _ratings(wrangling)
    split = wrangling.split_three(ratings, VALIDATION, TEST)
    assert wrangling.split_audit(split)["leakage"] == "pass"
    late = wrangling.ThreeWaySplit(
        validation_cutoff=7,
        test_cutoff=8,
        train=(*split.train, ratings[9]),
        validation=split.validation,
        test=split.test,
    )
    assert wrangling.split_audit(late)["leakage"] == "fail"
