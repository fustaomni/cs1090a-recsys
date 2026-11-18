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
from datetime import UTC, datetime
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


USER_COLUMNS = ("user_id", "gender", "age", "occupation", "zip_code")
# THE README'S OWN DOMAINS (A.328): gender M or F, age one of seven bucket codes, occupation 0
# to 20. The README says the demographics are self-reported and unchecked, so they are counted.
GENDERS = frozenset({"F", "M"})
AGE_CODES = frozenset({1, 18, 25, 35, 45, 50, 56})
OCCUPATIONS = range(21)
BYTES_PER_MEGABYTE = 1_000_000


@dataclass(frozen=True)
class Summary:
    count: int
    mean: float | None
    minimum: int | None
    maximum: int | None


def size_megabytes(path: Path) -> float:
    """The file's size in megabytes, a megabyte being one million bytes."""
    return path.stat().st_size / BYTES_PER_MEGABYTE


def summarize(values: tuple[int, ...]) -> Summary:
    """Count, mean, minimum and maximum; an empty column has none of the last three."""
    if not values:
        return Summary(0, None, None, None)
    return Summary(len(values), sum(values) / len(values), min(values), max(values))


def missing_by_column(path: Path, columns: tuple[str, ...]) -> dict[str, int]:
    """Empty fields per column, counted on the raw text before any field is parsed."""
    counts = dict.fromkeys(columns, 0)
    for row in _rows(path):
        for name, value in zip(columns, row, strict=True):
            counts[name] += 0 if value else 1
    return counts


def missing_by_group(path: Path, columns: tuple[str, ...], group: str) -> dict[str, int]:
    """Rows with any empty field, per value of one column, to see whether missingness follows it."""
    where = columns.index(group)
    counts: dict[str, int] = {}
    for row in _rows(path):
        counts[row[where]] = counts.get(row[where], 0) + (0 if all(row) else 1)
    return counts


def _five_digits(zip_code: str) -> bool:
    return len(zip_code) == 5 and zip_code.isdigit()


def unusual_users(users: tuple[User, ...]) -> dict[str, int]:
    """Values outside the README's documented domains, counted by the rule each breaks."""
    return {
        "gender-not-F-or-M": sum(u.gender not in GENDERS for u in users),
        "age-not-a-documented-code": sum(u.age not in AGE_CODES for u in users),
        "occupation-outside-0-to-20": sum(u.occupation not in OCCUPATIONS for u in users),
        "zip-not-five-digits": sum(not _five_digits(u.zip_code) for u in users),
    }


def time_cutoff(ratings: tuple[Rating, ...], fraction: float) -> int:
    """The timestamp at the training fraction: ratings strictly before it are the training set."""
    ordered = sorted(r.timestamp for r in ratings)
    return ordered[int(fraction * len(ordered))]


def rating_balance(ratings: tuple[Rating, ...]) -> dict[int, int]:
    """Ratings per star, every class from the lowest to the highest present even when empty."""
    counts = Counter(r.rating for r in ratings)
    return {star: counts.get(star, 0) for star in range(LOWEST, HIGHEST + 1)}


# THE JOINED TABLE (A.330): a rating's four fields, its user's four and its movie's two.
JOINED_COLUMNS = 10


def utc_date(stamp: int) -> str:
    """A Unix time as its UTC calendar date, YYYY-MM-DD."""
    return datetime.fromtimestamp(stamp, UTC).date().isoformat()


def joined_shape(
    ratings: tuple[Rating, ...], users: tuple[User, ...], movies: tuple[Movie, ...]
) -> tuple[int, int]:
    """Rows and columns of ratings joined to their user and movie; only known pairs join."""
    known_users = {u.user_id for u in users}
    known_movies = {m.movie_id for m in movies}
    rows = sum(r.user_id in known_users and r.movie_id in known_movies for r in ratings)
    return rows, JOINED_COLUMNS


@dataclass(frozen=True)
class ThreeWaySplit:
    validation_cutoff: int
    test_cutoff: int
    train: tuple[Rating, ...]
    validation: tuple[Rating, ...]
    test: tuple[Rating, ...]


def split_three(
    ratings: tuple[Rating, ...], validation_fraction: float, test_fraction: float
) -> ThreeWaySplit:
    """Training before the validation cut, validation up to the test cut, test from it (A.350).

    Both cuts are global time points at their quantiles, taken as time_cutoff takes them, so
    the test window is exactly split_at's at the test fraction: the delivered window is kept.
    """
    early = time_cutoff(ratings, validation_fraction)
    late = time_cutoff(ratings, test_fraction)
    if early > late:
        raise ValueError(f"the validation cut {early} falls after the test cut {late}")
    return ThreeWaySplit(
        validation_cutoff=early,
        test_cutoff=late,
        train=tuple(r for r in ratings if r.timestamp < early),
        validation=tuple(r for r in ratings if early <= r.timestamp < late),
        test=tuple(r for r in ratings if r.timestamp >= late),
    )


def _window(ratings: tuple[Rating, ...]) -> dict[str, int]:
    """A window's ratings, users, movies and its first and last time, refusing an empty one."""
    if not ratings:
        raise ValueError("a split window holds no rating")
    stamps = [r.timestamp for r in ratings]
    return {
        "ratings": len(ratings),
        "users": len({r.user_id for r in ratings}),
        "movies": len({r.movie_id for r in ratings}),
        "first": min(stamps),
        "last": max(stamps),
    }


def _unseen(before: tuple[Rating, ...], window: tuple[Rating, ...]) -> dict[str, int]:
    """How many of a window's ratings come from a user, or a movie, nothing before it rated."""
    users = {r.user_id for r in before}
    movies = {r.movie_id for r in before}
    return {
        "user-unseen": sum(r.user_id not in users for r in window),
        "movie-unseen": sum(r.movie_id not in movies for r in window),
    }


def split_audit(split: ThreeWaySplit) -> dict[str, object]:
    """Each window as data, and whether any rating sits outside its own window (A.350)."""
    early, late = split.validation_cutoff, split.test_cutoff
    leaked = (
        any(r.timestamp >= early for r in split.train)
        or any(not early <= r.timestamp < late for r in split.validation)
        or any(r.timestamp < late for r in split.test)
    )
    validation = {**_window(split.validation), **_unseen(split.train, split.validation)}
    test = {**_window(split.test), **_unseen(split.train + split.validation, split.test)}
    return {
        "windows": {"train": _window(split.train), "validation": validation, "test": test},
        "leakage": "fail" if leaked else "pass",
    }


def cold_start(split: Split) -> dict[str, int]:
    """Test ratings whose user, or whose movie, has no rating in the training set."""
    users = {r.user_id for r in split.train}
    movies = {r.movie_id for r in split.train}
    return {
        "test": len(split.test),
        "user-unseen": sum(r.user_id not in users for r in split.test),
        "movie-unseen": sum(r.movie_id not in movies for r in split.test),
    }


def ratings_per_user(ratings: tuple[Rating, ...]) -> dict[int, int]:
    """How many ratings each user who rated has made."""
    return dict(Counter(r.user_id for r in ratings))


def test_buckets(split: Split) -> dict[str, int]:
    """Each test rating in exactly one bucket by its user's and movie's training history."""
    users = {r.user_id for r in split.train}
    movies = {r.movie_id for r in split.train}
    buckets = dict.fromkeys(("warm", "new-user", "new-movie", "both-new"), 0)
    for r in split.test:
        user_seen, movie_seen = r.user_id in users, r.movie_id in movies
        if user_seen and movie_seen:
            buckets["warm"] += 1
        elif movie_seen:
            buckets["new-user"] += 1
        elif user_seen:
            buckets["new-movie"] += 1
        else:
            buckets["both-new"] += 1
    return buckets
