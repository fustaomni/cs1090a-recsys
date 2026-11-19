# tests/test_moe_fit.py
"""The gate of the mixture of experts is fitted, not drawn (A.360).

Model 15 on the site fits its gate on the validation window by gradient descent on the
mixture's squared error, the experts held fixed (site/src/mechanisms/lib/moefit.js). The model
in scripts/moe.py fits it the same way, so the page and the model agree on the same data.
"""

from __future__ import annotations

import importlib
import importlib.util
import math
from types import ModuleType

import pytest

from nonvacuous import nonempty

# The site's fitGate on the same toy data, copied from site/src/mechanisms/lib/moefit.js.
SITE_THETA = (
    (-1.5902530111234223, 0.5522430773281715, 0.622887727090787),
    (1.5902530111234223, -0.5522430773281717, -0.6228877270907865),
)


def _subject() -> ModuleType:
    found = importlib.util.find_spec("moe")
    assert found is not None, "scripts/moe.py does not exist"
    return importlib.import_module("moe")


Toy = tuple[tuple[object, ...], tuple[tuple[float, ...], ...], tuple[float, ...]]


def _toy(subject: ModuleType) -> Toy:
    """Two experts, each right in its own region: a fitted gate must learn to route."""
    features: list[object] = []
    predictions: list[tuple[float, ...]] = []
    targets: list[float] = []
    for index in range(40):
        warm = index % 2 == 0
        count = (20, 30) if warm else (0, 0)
        features.append(subject.GateFeatures(user_count=count[0], movie_count=count[1]))
        predictions.append((4.0, 3.0) if warm else (3.0, 2.0))
        targets.append(4.0 if warm else 2.0)
    return tuple(features), tuple(predictions), tuple(targets)


def test_the_fitted_gate_cuts_the_uniform_gates_error_by_four_times() -> None:
    subject = _subject()
    _, losses = subject.fit_gate(*_toy(subject))
    assert losses[-1] < losses[0] / 4, (losses[0], losses[-1])


def test_the_fitted_gate_routes_each_region_to_its_expert() -> None:
    subject = _subject()
    features, predictions, targets = _toy(subject)
    theta, _ = subject.fit_gate(features, predictions, targets)
    rows = tuple(zip(features, predictions, targets, strict=True))
    for feature, prediction, target in nonempty(rows):
        mixed = subject.mix(prediction, subject.fitted_weights(theta, feature))
        assert abs(mixed - target) < 0.2, (feature, mixed)


def test_the_fitted_gate_agrees_with_the_site() -> None:
    subject = _subject()
    theta, _ = subject.fit_gate(*_toy(subject))
    for row, site in nonempty(tuple(zip(theta, SITE_THETA, strict=True))):
        for value, expected in nonempty(tuple(zip(row, site, strict=True))):
            assert math.isclose(value, expected, abs_tol=1e-9), (theta, SITE_THETA)


def test_a_gate_is_never_fitted_on_no_ratings() -> None:
    subject = _subject()
    with pytest.raises(ValueError, match="at least one rating"):
        subject.fit_gate((), (), ())
