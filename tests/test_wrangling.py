# tests/test_wrangling.py
"""MovieLens 1M is read, judged and split by pure functions the notebook only calls (A.326).

Every proof writes its own rows in the dataset's own format, so nothing here reads the real
archive. The quality rules give pass, fail or unknown with a count; the split is one absolute
time point; a feature computed from a rating at or after it is refused.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

USERS = ("1::F::1::10::48067", "2::M::56::16::70072")
MOVIES = (
    "1193::One Flew Over the Cuckoo's Nest (1975)::Drama",
    "661::James and the Giant Peach (1996)::Animation|Children's|Musical",
    "1357::Shine (1996)::Drama|Romance",
)
RATINGS = (
    "1::1193::5::978300760",
    "1::661::3::978302109",
    "2::1357::5::978298709",
    "2::1193::4::978299000",
)
CUTOFF = 978300000


def _subject() -> ModuleType:
    found = importlib.util.find_spec("wrangling")
    assert found is not None, "scripts/wrangling.py does not exist yet"
    return importlib.import_module("wrangling")


def _file(directory: Path, name: str, rows: tuple[str, ...]) -> Path:
    path = directory / name
    path.write_bytes(("\n".join(rows) + "\n").encode("latin-1"))
    return path


def _write(directory: Path) -> tuple[Path, Path, Path]:
    return (
        _file(directory, "ratings.dat", RATINGS),
        _file(directory, "users.dat", USERS),
        _file(directory, "movies.dat", MOVIES),
    )


def test_the_three_tables_load_with_their_documented_columns_and_types(tmp_path: Path) -> None:
    wrangling = _subject()
    ratings, users, movies = _write(tmp_path)
    loaded = wrangling.read_ratings(ratings)
    assert len(loaded) == len(RATINGS), loaded
    first = loaded[0]
    observed = (first.user_id, first.movie_id, first.rating, first.timestamp)
    assert observed == (1, 1193, 5, 978300760), observed
    user = wrangling.read_users(users)[1]
    assert (user.user_id, user.gender, user.age, user.occupation, user.zip_code) == (
        2,
        "M",
        56,
        16,
        "70072",
    )
    movie = wrangling.read_movies(movies)[1]
    title = "James and the Giant Peach (1996)"
    genres = ("Animation", "Children's", "Musical")
    assert (movie.movie_id, movie.title, movie.genres) == (661, title, genres), movie


def test_each_quality_rule_reports_pass_fail_or_unknown_with_its_count(tmp_path: Path) -> None:
    wrangling = _subject()
    ratings, users, movies = _write(tmp_path)
    people, catalogue = wrangling.read_users(users), wrangling.read_movies(movies)
    report = wrangling.judge(wrangling.read_ratings(ratings), people, catalogue)
    assert report.contract == "ratings-quality/v1", report
    kinds = {rule.kind for rule in report.rules}
    assert kinds == {"validity", "uniqueness", "referential-integrity", "completeness"}, kinds
    statuses = [(rule.status, rule.count) for rule in report.rules]
    assert statuses == [("pass", 0)] * len(statuses), statuses
    empty = wrangling.judge((), people, catalogue)
    assert {rule.status for rule in empty.rules} == {"unknown"}, empty


def test_a_rating_outside_one_to_five_or_an_orphan_user_fails_its_rule(tmp_path: Path) -> None:
    wrangling = _subject()
    _, users, movies = _write(tmp_path)
    rows = (*RATINGS, "1::1357::6::978302200", "99::1193::4::978302300")
    bad = wrangling.read_ratings(_file(tmp_path, "bad.dat", rows))
    report = wrangling.judge(bad, wrangling.read_users(users), wrangling.read_movies(movies))
    named = {rule.name: (rule.status, rule.count) for rule in report.rules}
    assert named["rating-in-range"] == ("fail", 1), named
    assert named["rating-user-exists"] == ("fail", 1), named
    assert named["rating-movie-exists"] == ("pass", 0), named


def test_the_temporal_split_puts_every_training_rating_before_the_cutoff(tmp_path: Path) -> None:
    wrangling = _subject()
    loaded = wrangling.read_ratings(_write(tmp_path)[0])
    split = wrangling.split_at(loaded, CUTOFF)
    assert split.train and split.test, split
    assert max(r.timestamp for r in split.train) < CUTOFF <= min(r.timestamp for r in split.test)
    assert len(split.train) + len(split.test) == len(loaded), split
    assert set(split.train) | set(split.test) == set(loaded), split


def test_a_feature_computed_from_a_later_rating_is_refused(tmp_path: Path) -> None:
    wrangling = _subject()
    loaded = wrangling.read_ratings(_write(tmp_path)[0])
    with pytest.raises(wrangling.LeakageError):
        wrangling.user_means(loaded, CUTOFF)
    assert wrangling.user_means(wrangling.split_at(loaded, CUTOFF).train, CUTOFF) == {2: 4.5}


def test_the_raw_files_are_never_modified(tmp_path: Path) -> None:
    wrangling = _subject()
    paths = _write(tmp_path)
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    loaded = wrangling.read_ratings(paths[0])
    wrangling.judge(loaded, wrangling.read_users(paths[1]), wrangling.read_movies(paths[2]))
    wrangling.split_at(loaded, CUTOFF)
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert after == before, (before, after)
