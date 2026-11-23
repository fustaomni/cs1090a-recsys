# tests/test_statistical_evaluation.py
"""The statistical evaluation package produces comparison evidence and never a decision (A.303).

The paired improvement's interval comes from a bootstrap over users, never ratings, so a user who
rated more cannot narrow it; the exploratory comparisons are Holm adjusted; and the test window
is read exactly once, a second evaluation refused by name.
"""

from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType

import pytest

import evaluation_contracts
import independent_evaluator


def _subject() -> ModuleType:
    found = importlib.util.find_spec("statistical_evaluation")
    assert found is not None, "scripts/statistical_evaluation.py does not exist"
    return importlib.import_module("statistical_evaluation")


def _rows(subject: ModuleType, copies: int = 1) -> list[object]:
    losses = {1: (0.9, 1.4), 2: (1.1, 1.0), 3: (0.4, 1.2), 4: (0.8, 0.9), 5: (1.3, 1.6)}
    rows: list[object] = []
    for user, (model_loss, baseline_loss) in losses.items():
        for shift in (0.0, 0.2) * copies:
            rows.append(
                subject.PairedLoss(
                    user=user, model_loss=model_loss + shift, baseline_loss=baseline_loss + shift
                )
            )
    return rows


def test_the_paired_interval_resamples_users_not_ratings() -> None:
    """Repeating every user's ratings leaves each user's mean, and so the interval, unchanged."""
    subject = _subject()
    once = subject.compare("moe", "bias", _rows(subject), resamples=2000, seed=7, alpha=0.05)
    thrice = subject.compare(
        "moe", "bias", _rows(subject, copies=3), resamples=2000, seed=7, alpha=0.05
    )
    assert isinstance(once, evaluation_contracts.ComparisonEvidence)
    assert once.interval_method is evaluation_contracts.IntervalMethod.USER_BOOTSTRAP
    assert (once.estimate, once.low, once.high) == (thrice.estimate, thrice.low, thrice.high)
    assert once.low < once.estimate < once.high
    assert once.p_value == thrice.p_value


def test_exploratory_comparisons_are_holm_adjusted() -> None:
    subject = _subject()
    adjusted = subject.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})
    assert subject.holm({"only": 0.7, "other": 0.9}) == pytest.approx({"only": 1.0, "other": 1.0})


def test_the_test_window_is_evaluated_once() -> None:
    subject = _subject()
    held_out = (independent_evaluator.Observation(user=1, movie=2, time=3, rating=4),)
    window = subject.TestWindow(held_out)
    assert window.open() == held_out
    with pytest.raises(subject.TestWindowSpentError):
        window.open()
