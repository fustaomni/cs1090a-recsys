"""data:fetch (A.100): an archive is verified against its published MD5 before it is unpacked."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

import spine
from data_fetch import ENTRYPOINT, POLICY, REQUIRED, _download, fetch, observe

# Planted text is joined with chr(10): no escape sequence crosses a layer (M60).
NEWLINE = chr(10)


def _local(url: str, target: Path) -> None:
    """The proofs' transport: the url is a local path, copied byte for byte."""
    target.write_bytes(Path(url).read_bytes())


def _archive(
    tmp_path: Path, names: tuple[str, ...] = REQUIRED, md5: str | None = None
) -> tuple[str, str]:
    archive = tmp_path / "ml-1m.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name in names:
            bundle.writestr(name, f"{name} rows{NEWLINE}")
    digest = md5 or hashlib.md5(archive.read_bytes(), usedforsecurity=False).hexdigest()
    sums = tmp_path / "ml-1m.zip.md5"
    sums.write_text(f"MD5 (ml-1m.zip) = {digest}{NEWLINE}", encoding="utf-8")
    return str(archive), str(sums)


def test_a_matching_archive_is_extracted_with_every_file_fingerprinted(tmp_path: Path) -> None:
    archive_url, md5_url = _archive(tmp_path)
    destination = tmp_path / "data"
    record, refusals = fetch(archive_url, md5_url, destination, download=_local)
    assert refusals == []
    assert record.md5_observed == record.md5_published
    assert {entry.name for entry in record.files} == set(REQUIRED)
    for entry in record.files:
        written = (destination / entry.name).read_bytes()
        assert hashlib.sha256(written).hexdigest() == entry.sha256


def test_an_archive_whose_md5_differs_is_refused_and_nothing_is_extracted(
    tmp_path: Path,
) -> None:
    archive_url, md5_url = _archive(tmp_path, md5="0" * 32)
    destination = tmp_path / "data"
    _, refusals = fetch(archive_url, md5_url, destination, download=_local)
    assert "ERR_DATA_CHECKSUM_MISMATCH" in refusals
    assert not destination.exists() or not any(destination.iterdir())


def test_an_archive_missing_a_required_file_is_refused(tmp_path: Path) -> None:
    archive_url, md5_url = _archive(tmp_path, names=REQUIRED[:2])
    _, refusals = fetch(archive_url, md5_url, tmp_path / "data", download=_local)
    assert "ERR_DATA_FILES_MISSING" in refusals


def test_an_absent_fetch_is_refused_by_the_policy(tmp_path: Path) -> None:
    archive_url, md5_url = _archive(tmp_path)
    record = observe(archive_url, md5_url, tmp_path / "staging", download=_local)
    found = spine.evaluate(record, "absent", POLICY, ENTRYPOINT)
    refused = {rule.code for rule in found.rules if rule.outcome == "fail"}
    assert "ERR_DATA_INPUT_MISSING" in refused


def test_a_url_that_is_not_https_is_refused(tmp_path: Path) -> None:
    archive_url, _ = _archive(tmp_path)
    with pytest.raises(SystemExit, match="refusing to download"):
        _download(Path(archive_url).as_uri(), tmp_path / "copy.zip")
    assert not (tmp_path / "copy.zip").exists()
