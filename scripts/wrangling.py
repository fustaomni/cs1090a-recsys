# scripts/wrangling.py
"""Milestone 2's wrangling: MovieLens 1M read, judged and split by pure functions (A.326).

The notebook only calls these. Each reader returns typed, immutable records and writes nothing;
judge reports ratings-quality/v1, each rule pass or fail with the count it found, or unknown when
there is nothing to judge; the split is one absolute time point, so no training rating comes
after a test rating, the split 2026 recommender evaluation names as the one that cannot leak.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Status = Literal["pass", "fail", "unknown"]
Kind = Literal["validity", "uniqueness", "referential-integrity", "completeness"]
SEPARATOR = "::"
# MOVIELENS 1M IS LATIN-1, NOT UTF-8: a few titles carry accented characters in that encoding.
ENCODING = "latin-1"
LOWEST, HIGHEST = 1, 5


class LeakageError(ValueError):
    """A feature would be computed from a rating at or after the split's cutoff."""


@dataclass(frozen=True, order=True)
class Rating:
    user_id: int
    movie_id: int
    rating: int
    timestamp: int


@dataclass(frozen=True)
class User:
    user_id: int
    gender: str
    age: int
    occupation: int
    zip_code: str


@dataclass(frozen=True)
class Movie:
    movie_id: int
    title: str
    genres: tuple[str, ...]


@dataclass(frozen=True)
class Rule:
    name: str
    kind: Kind
    status: Status
    count: int


@dataclass(frozen=True)
class Quality:
    rules: tuple[Rule, ...]
    contract: str = "ratings-quality/v1"


@dataclass(frozen=True)
class Split:
    cutoff: int
    train: tuple[Rating, ...]
    test: tuple[Rating, ...]


def _rows(path: Path) -> list[list[str]]:
    text = path.read_text(encoding=ENCODING)
    return [line.split(SEPARATOR) for line in text.splitlines() if line]


def read_ratings(path: Path) -> tuple[Rating, ...]:
    """ratings.dat: UserID::MovieID::Rating::Timestamp, one rating per line."""
    return tuple(Rating(int(u), int(m), int(r), int(t)) for u, m, r, t in _rows(path))


def read_users(path: Path) -> tuple[User, ...]:
    """users.dat: UserID::Gender::Age::Occupation::Zip-code, one user per line."""
    return tuple(User(int(u), g, int(a), int(o), z) for u, g, a, o, z in _rows(path))


def read_movies(path: Path) -> tuple[Movie, ...]:
    """movies.dat: MovieID::Title::Genres, the genres separated by a pipe."""
    return tuple(
        Movie(int(m), title, tuple(genres.split("|")) if genres else ())
        for m, title, genres in _rows(path)
    )


def _rule(name: str, kind: Kind, ratings: tuple[Rating, ...], failed: int) -> Rule:
    if not ratings:
        return Rule(name, kind, "unknown", 0)
    return Rule(name, kind, "fail" if failed else "pass", failed)


def judge(
    ratings: tuple[Rating, ...], users: tuple[User, ...], movies: tuple[Movie, ...]
) -> Quality:
    """ratings-quality/v1: one rule per check, each with its status and the count it found."""
    people = {user.user_id for user in users}
    known_movies = {movie.movie_id for movie in movies}
    pairs = Counter((r.user_id, r.movie_id) for r in ratings)
    out_of_range = sum(not LOWEST <= r.rating <= HIGHEST for r in ratings)
    repeated = sum(count - 1 for count in pairs.values())
    orphan_users = sum(r.user_id not in people for r in ratings)
    orphan_movies = sum(r.movie_id not in known_movies for r in ratings)
    blank = sum(not u.gender or not u.zip_code for u in users) + sum(not m.title for m in movies)
    return Quality(
        rules=(
            _rule("rating-in-range", "validity", ratings, out_of_range),
            _rule("user-movie-unique", "uniqueness", ratings, repeated),
            _rule("rating-user-exists", "referential-integrity", ratings, orphan_users),
            _rule("rating-movie-exists", "referential-integrity", ratings, orphan_movies),
            _rule("fields-present", "completeness", ratings, blank),
        )
    )


def split_at(ratings: tuple[Rating, ...], cutoff: int) -> Split:
    """Training strictly before the cutoff, test at or after it: one absolute time point."""
    train = tuple(r for r in ratings if r.timestamp < cutoff)
    test = tuple(r for r in ratings if r.timestamp >= cutoff)
    return Split(cutoff=cutoff, train=train, test=test)


def user_means(ratings: tuple[Rating, ...], cutoff: int) -> dict[int, float]:
    """Each user's mean rating, refused when any rating is at or after the cutoff."""
    late = [r for r in ratings if r.timestamp >= cutoff]
    if late:
        raise LeakageError(f"{len(late)} rating(s) at or after the cutoff {cutoff}")
    given: dict[int, list[int]] = {}
    for r in ratings:
        given.setdefault(r.user_id, []).append(r.rating)
    return {user: sum(scores) / len(scores) for user, scores in given.items()}
