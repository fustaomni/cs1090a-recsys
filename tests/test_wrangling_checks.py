# tests/test_wrangling_checks.py
"""Every cleaning check the Milestone 2 brief lists is a pure function of the raw files (A.328).

Size, summary statistics, missing fields per column and by group, impossible demographic values
by the rule each breaks, and every rating class: each is computed here on rows the test writes,
so the notebook only calls them and reports each finding with its decision.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType


def _subject(name: str) -> ModuleType:
    module = importlib.import_module("wrangling")
    assert hasattr(module, name), f"wrangling has no {name} yet"
    return module


def _file(directory: Path, name: str, rows: tuple[str, ...]) -> Path:
    path = directory / name
    path.write_bytes(("\n".join(rows) + "\n").encode("latin-1"))
    return path


def test_the_archive_size_is_reported_in_megabytes(tmp_path: Path) -> None:
    wrangling = _subject("size_megabytes")
    archive = tmp_path / "ml-1m.zip"
    archive.write_bytes(b"\0" * 2_500_000)
    assert wrangling.size_megabytes(archive) == 2.5


def test_each_numerical_column_is_summarised_by_count_mean_minimum_and_maximum() -> None:
    wrangling = _subject("summarize")
    found = wrangling.summarize((1, 2, 3, 6))
    assert (found.count, found.mean, found.minimum, found.maximum) == (4, 3.0, 1, 6), found
    empty = wrangling.summarize(())
    assert (empty.count, empty.mean, empty.minimum, empty.maximum) == (0, None, None, None)


def test_missing_values_are_counted_per_column_and_by_group(tmp_path: Path) -> None:
    wrangling = _subject("missing_by_group")
    rows = ("1::F::1::10::48067", "2::M::56::16::", "3::M::25::::02138")
    users = _file(tmp_path, "users.dat", rows)
    missing = wrangling.missing_by_column(users, wrangling.USER_COLUMNS)
    expected = {"user_id": 0, "gender": 0, "age": 0, "occupation": 1, "zip_code": 1}
    assert missing == expected, missing
    grouped = wrangling.missing_by_group(users, wrangling.USER_COLUMNS, "gender")
    assert grouped == {"F": 0, "M": 2}, grouped


def test_impossible_demographic_values_are_counted_by_rule(tmp_path: Path) -> None:
    wrangling = _subject("unusual_users")
    rows = ("1::F::1::10::48067", "2::X::57::21::7007", "3::M::25::20::02138-1234")
    found = wrangling.unusual_users(wrangling.read_users(_file(tmp_path, "users.dat", rows)))
    expected = {
        "gender-not-F-or-M": 1,
        "age-not-a-documented-code": 1,
        "occupation-outside-0-to-20": 1,
        "zip-not-five-digits": 2,
    }
    assert found == expected, found


def test_every_rating_class_is_counted_even_when_empty(tmp_path: Path) -> None:
    wrangling = _subject("rating_balance")
    rows = ("1::1::5::1", "1::2::5::2", "2::1::3::3")
    ratings = wrangling.read_ratings(_file(tmp_path, "ratings.dat", rows))
    assert wrangling.rating_balance(ratings) == {1: 0, 2: 0, 3: 1, 4: 0, 5: 2}


def test_the_cutoff_is_the_timestamp_at_the_training_fraction(tmp_path: Path) -> None:
    wrangling = _subject("time_cutoff")
    stamps = range(10, 0, -1)
    rows = tuple(f"1::{movie}::4::{stamp}" for movie, stamp in enumerate(stamps))
    ratings = wrangling.read_ratings(_file(tmp_path, "ratings.dat", rows))
    assert wrangling.time_cutoff(ratings, 0.8) == 9
    assert len(wrangling.split_at(ratings, wrangling.time_cutoff(ratings, 0.8)).train) == 8
