# tests/test_moe.py
"""A gated mixture of experts predicts each rating (A.345).

The gate is a softmax over features computed strictly before the rating, so its weights are
non-negative and sum to one even for an extreme logit; a gate collapsed onto one expert
reproduces that expert; no gate feature reads the test window; and each cold-start bucket
reports the mixture's RMSE beside the bias baseline's.
"""

from __future__ import annotations

import importlib
import importlib.util
import math
from types import ModuleType

import pytest

from wrangling import Rating


def _subject() -> ModuleType:
    found = importlib.util.find_spec("moe")
    assert found is not None, "scripts/moe.py does not exist"
    return importlib.import_module("moe")


def test_gate_weights_are_non_negative_and_sum_to_one() -> None:
    subject = _subject()
    # PAST FLOAT64'S EXP LIMIT (about 709.78): without the max-logit subtraction this overflows.
    weights = subject.gate_weights((2.0, -1.0, 0.5, 1000.0))
    assert all(weight >= 0.0 for weight in weights), weights
    assert math.isclose(sum(weights), 1.0), weights


def test_a_gate_collapsed_to_one_expert_reproduces_that_expert() -> None:
    subject = _subject()
    experts = (3.1, 4.4, 2.2, 3.9)
    for chosen, expected in enumerate(experts):
        logits = tuple(50.0 if index == chosen else -50.0 for index in range(len(experts)))
        mixed = subject.mix(experts, subject.gate_weights(logits))
        assert math.isclose(mixed, expected, abs_tol=1e-9), (chosen, mixed)


def test_no_gate_feature_reads_the_test_window() -> None:
    subject = _subject()
    training = (Rating(1, 10, 4, 100), Rating(2, 10, 3, 200))
    target = Rating(1, 10, 5, 500)
    subject.gate_features(training, target, boundary=300)
    with pytest.raises(subject.LeakageError, match="300"):
        subject.gate_features((*training, Rating(3, 10, 1, 300)), target, boundary=300)


def test_each_bucket_reports_its_rmse_beside_the_baseline() -> None:
    subject = _subject()
    rows = (("warm", 4.0, 3.0, 4.0), ("warm", 2.0, 3.0, 4.0), ("new-user", 3.0, 3.5, 5.0))
    report = subject.bucket_report(rows)
    assert report["warm"] == {"rmse": math.sqrt(2.0), "baseline_rmse": 1.0}, report
    assert report["new-user"] == {"rmse": 2.0, "baseline_rmse": 1.5}, report
