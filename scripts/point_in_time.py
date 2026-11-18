# scripts/point_in_time.py
"""Every feature is point-in-time correct, stricter than an inclusive bound (A.292).

MovieLens stamps ratings to the second and seconds collide, so a feature for a rating reads
only ratings dated strictly before it: a same-second rating, the target among them, never feeds
the target's own features, and a feature source dated at or after its target is refused.
"""

from __future__ import annotations

from dataclasses import dataclass

from wrangling import LeakageError, Rating

__all__ = ["Features", "LeakageError", "audit", "features_before"]


@dataclass(frozen=True)
class Features:
    """A rating's user and movie history, counted and averaged from strictly earlier ratings."""

    user_count: int
    user_mean: float | None
    movie_count: int
    movie_mean: float | None


def audit(sources: tuple[Rating, ...], target: Rating) -> None:
    """Refuse any source dated at or after the target, one-second ties included."""
    late = [r for r in sources if r.timestamp >= target.timestamp]
    if late:
        raise LeakageError(
            f"{len(late)} source rating(s) at or after the target's time {target.timestamp}"
        )


def _mean(scores: list[int]) -> float | None:
    return sum(scores) / len(scores) if scores else None


def features_before(ratings: tuple[Rating, ...], target: Rating) -> Features:
    """The target's features from ratings strictly before it, audited before they are used."""
    earlier = tuple(r for r in ratings if r.timestamp < target.timestamp)
    audit(earlier, target)
    users = [r.rating for r in earlier if r.user_id == target.user_id]
    movies = [r.rating for r in earlier if r.movie_id == target.movie_id]
    return Features(len(users), _mean(users), len(movies), _mean(movies))
