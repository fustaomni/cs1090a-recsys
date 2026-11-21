# scripts/bitemporal.py
"""Every rating carries two times, its event time and its observation time (A.300).

MovieLens 1M records only the event time, when a user rated a movie. A time-ordered replay
therefore declares its observation-time assumption, how long after the event the system
learned of the rating, and a feature source observed at or after the prediction time is
refused even when its event came earlier, the same strict bound A.292 applies to event time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from wrangling import LeakageError, Rating

__all__ = ["LeakageError", "Observed", "ReplayAssumption", "audit_observed", "observe"]


@dataclass(frozen=True)
class ReplayAssumption:
    """When the replay holds the system learned of a rating: its event time plus a lag."""

    lag_seconds: int

    def __post_init__(self) -> None:
        if self.lag_seconds < 0:
            raise ValueError(f"a rating cannot be observed before it happened: {self.lag_seconds}")


@dataclass(frozen=True)
class Observed:
    """A rating with both of its times."""

    rating: Rating
    event_time: int
    observation_time: int


def observe(ratings: Sequence[Rating], assumption: ReplayAssumption) -> tuple[Observed, ...]:
    """Each rating with its event time and the observation time the assumption gives it."""
    lag = assumption.lag_seconds
    return tuple(Observed(each, each.timestamp, each.timestamp + lag) for each in ratings)


def audit_observed(sources: Sequence[Observed], prediction_time: int) -> None:
    """Refuse any source the system had not observed strictly before the prediction time."""
    late = [each for each in sources if each.observation_time >= prediction_time]
    if late:
        message = f"{len(late)} source(s) observed at or after prediction time {prediction_time}"
        raise LeakageError(message)
