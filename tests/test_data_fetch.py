"""data:fetch (A.100): an archive is verified against its published MD5 before it is unpacked."""

from __future__ import annotations

import hashlib
import io
import urllib.error
import urllib.request
import zipfile
from datetime import date
from http.client import HTTPMessage
from pathlib import Path

import pytest

import data_fetch
import spine
from data_fetch import (
    ARCHIVE_URL,
    ENTRYPOINT,
    POLICY,
    REQUIRED,
    DataFile,
    DataPin,
    _download,
    fetch,
    load_pin,
    observe,
)
from nonvacuous import nonempty

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


def _hostile(tmp_path: Path, member: zipfile.ZipInfo) -> tuple[str, str]:
    """The required members plus one hostile member, and the MD5 file that matches them."""
    archive = tmp_path / "ml-1m.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name in REQUIRED:
            bundle.writestr(name, f"{name} rows{NEWLINE}")
        bundle.writestr(member, "planted")
    digest = hashlib.md5(archive.read_bytes(), usedforsecurity=False).hexdigest()
    sums = tmp_path / "ml-1m.zip.md5"
    sums.write_text(f"MD5 (ml-1m.zip) = {digest}{NEWLINE}", encoding="utf-8")
    return str(archive), str(sums)


def _pin(archive_url: str) -> DataPin:
    """The pin a reviewer would commit for this test's own archive."""
    data = Path(archive_url).read_bytes()
    with zipfile.ZipFile(archive_url) as bundle:
        files = tuple(
            DataFile(name=name, sha256=hashlib.sha256(bundle.read(name)).hexdigest())
            for name in bundle.namelist()
        )
    return DataPin(
        archive_url=ARCHIVE_URL,
        archive_sha256=hashlib.sha256(data).hexdigest(),
        files=files,
        first_fetched="2026-11-06",
        md5_corroborated=hashlib.md5(data, usedforsecurity=False).hexdigest(),
        reviewed_commit="0" * 40,
    )


def test_a_matching_archive_is_extracted_with_every_file_fingerprinted(tmp_path: Path) -> None:
    archive_url, md5_url = _archive(tmp_path)
    destination = tmp_path / "data"
    pin = _pin(archive_url)
    record, refusals = fetch(archive_url, md5_url, destination, download=_local, pin=pin)
    assert refusals == []
    assert record is not None
    assert record.md5_observed == record.md5_published
    assert {entry.name for entry in record.files} == set(REQUIRED)
    for entry in nonempty(record.files):
        written = (destination / entry.name).read_bytes()
        assert hashlib.sha256(written).hexdigest() == entry.sha256


def test_an_archive_whose_md5_differs_is_refused_and_nothing_is_extracted(
    tmp_path: Path,
) -> None:
    archive_url, md5_url = _archive(tmp_path, md5="0" * 32)
    destination = tmp_path / "data"
    _, refusals = fetch(archive_url, md5_url, destination, download=_local, pin=_pin(archive_url))
    assert "ERR_DATA_CHECKSUM_MISMATCH" in refusals
    assert not destination.exists() or not any(destination.iterdir())


def test_an_archive_missing_a_required_file_is_refused(tmp_path: Path) -> None:
    archive_url, md5_url = _archive(tmp_path, names=REQUIRED[:2])
    pin = _pin(archive_url)
    _, refusals = fetch(archive_url, md5_url, tmp_path / "data", download=_local, pin=pin)
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


def test_an_archive_that_misses_its_sha256_pin_is_never_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pin is checked before the archive is opened, so a mismatch reads nothing (A.235)."""
    archive_url, md5_url = _archive(tmp_path)
    wrong = _pin(archive_url).model_copy(update={"archive_sha256": "0" * 64})
    opened: list[str] = []
    real = zipfile.ZipFile

    def spy(file: str | Path) -> zipfile.ZipFile:
        opened.append(str(file))
        return real(file)

    monkeypatch.setattr(data_fetch.zipfile, "ZipFile", spy)
    _, refusals = fetch(archive_url, md5_url, tmp_path / "data", download=_local, pin=wrong)
    assert "ERR_DATA_PIN_MISMATCH" in refusals, refusals
    assert opened == [], opened


def test_a_matching_md5_never_admits_an_archive_that_misses_its_sha256_pin(
    tmp_path: Path,
) -> None:
    """The publisher's MD5 guards against corruption only; the reviewed pin decides (A.235)."""
    archive_url, md5_url = _archive(tmp_path)
    wrong = _pin(archive_url).model_copy(update={"archive_sha256": "0" * 64})
    destination = tmp_path / "data"
    _, refusals = fetch(archive_url, md5_url, destination, download=_local, pin=wrong)
    assert "ERR_DATA_CHECKSUM_MISMATCH" not in refusals, refusals
    assert "ERR_DATA_PIN_MISMATCH" in refusals, refusals
    assert not destination.exists() or not any(destination.iterdir())


def test_a_redirect_to_another_host_or_a_plain_http_origin_is_refused(tmp_path: Path) -> None:
    """Only the allow-listed HTTPS origin is fetched from, before or after a redirect (A.235)."""
    handler = data_fetch.SameOriginRedirects()
    request = urllib.request.Request("https://files.grouplens.org/datasets/movielens/ml-1m.zip")
    assert request.full_url == ARCHIVE_URL, request.full_url
    plain = ARCHIVE_URL.replace("https://", "http://", 1)
    for target in ("https://elsewhere.example/ml-1m.zip", plain):
        with pytest.raises(urllib.error.HTTPError, match="refused"):
            handler.redirect_request(request, io.BytesIO(), 302, "Found", HTTPMessage(), target)
    same = ARCHIVE_URL.replace("ml-1m.zip", "ml-1m-mirror.zip")
    followed = handler.redirect_request(request, io.BytesIO(), 302, "Found", HTTPMessage(), same)
    assert followed is not None and followed.full_url == same, followed
    with pytest.raises(SystemExit, match="refusing to download"):
        _download("https://elsewhere.example/ml-1m.zip", tmp_path / "copy.zip")
    assert not (tmp_path / "copy.zip").exists()


def test_a_traversing_absolute_or_link_member_is_refused(tmp_path: Path) -> None:
    """Every member is inspected before anything is written, even one never extracted (A.235)."""
    link = zipfile.ZipInfo("ml-1m/link")
    link.external_attr = 0o120777 << 16
    backslash = zipfile.ZipInfo("..\\escape.txt")
    hostile = (zipfile.ZipInfo("../escape.txt"), zipfile.ZipInfo("/abs.txt"), backslash, link)
    for index, member in enumerate(hostile):
        case = tmp_path / str(index)
        case.mkdir()
        archive_url, md5_url = _hostile(case, member)
        destination = case / "data"
        pin = _pin(archive_url)
        _, refusals = fetch(archive_url, md5_url, destination, download=_local, pin=pin)
        assert "ERR_DATA_MEMBER_UNSAFE" in refusals, (member.filename, refusals)
        assert not destination.exists() or not any(destination.iterdir())
    assert not (tmp_path / "escape.txt").exists()


def test_an_archive_over_its_size_or_count_limit_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An archive is bounded in members and unpacked bytes, judged from its own record (A.235)."""
    archive_url, md5_url = _archive(tmp_path)
    pin = _pin(archive_url)
    monkeypatch.setattr(data_fetch, "MAX_MEMBERS", len(REQUIRED) - 1)
    _, refusals = fetch(archive_url, md5_url, tmp_path / "count", download=_local, pin=pin)
    assert "ERR_DATA_ARCHIVE_OVER_LIMIT" in refusals, refusals
    monkeypatch.setattr(data_fetch, "MAX_MEMBERS", 16)
    monkeypatch.setattr(data_fetch, "MAX_TOTAL_BYTES", 1)
    _, refusals = fetch(archive_url, md5_url, tmp_path / "size", download=_local, pin=pin)
    assert "ERR_DATA_ARCHIVE_OVER_LIMIT" in refusals, refusals


def test_an_interrupted_download_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fetch interrupted part-way leaves no published file and no staging behind (A.235)."""
    archive_url, md5_url = _archive(tmp_path)
    pin = _pin(archive_url)
    destination = tmp_path / "data"
    real = Path.write_bytes

    def flaky(self: Path, data: bytes) -> int:
        if self.name == "movies.dat":
            raise OSError("interrupted")
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky)
    with pytest.raises(OSError, match="interrupted"):
        fetch(archive_url, md5_url, destination, download=_local, pin=pin)
    assert not destination.exists(), sorted(destination.rglob("*"))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["ml-1m.zip", "ml-1m.zip.md5"]


def test_a_stalled_download_times_out_and_retries_a_bounded_number_of_times(
    tmp_path: Path,
) -> None:
    """Each attempt has a deadline, and the attempts and the waits between them are bounded."""
    timeouts: list[float] = []
    waits: list[float] = []

    def stalled(url: str, timeout: float) -> bytes:
        timeouts.append(timeout)
        raise TimeoutError("stalled")

    target = tmp_path / "copy.zip"
    with pytest.raises(SystemExit, match="gave up"):
        _download(ARCHIVE_URL, target, read=stalled, sleep=waits.append)
    assert timeouts == [data_fetch.TIMEOUT_SECONDS] * data_fetch.ATTEMPTS, timeouts
    expected = [data_fetch.BACKOFF_SECONDS * 2**n for n in range(data_fetch.ATTEMPTS - 1)]
    assert waits == expected, waits
    assert not target.exists()


def test_a_verified_published_copy_makes_a_rerun_a_no_op(tmp_path: Path) -> None:
    """A rerun downloads nothing while every published file matches its pin (A.235)."""
    archive_url, md5_url = _archive(tmp_path)
    pin = _pin(archive_url)
    destination = tmp_path / "data"
    _, refusals = fetch(archive_url, md5_url, destination, download=_local, pin=pin)
    assert refusals == [], refusals
    fetched: list[str] = []

    def counting(url: str, target: Path) -> None:
        fetched.append(url)
        _local(url, target)

    _, refusals = fetch(archive_url, md5_url, destination, download=counting, pin=pin)
    assert refusals == [] and fetched == [], (refusals, fetched)
    (destination / REQUIRED[0]).write_bytes(b"tampered")
    _, refusals = fetch(archive_url, md5_url, destination, download=counting, pin=pin)
    assert refusals == [] and fetched, (refusals, fetched)
    assert (destination / REQUIRED[0]).read_bytes() != b"tampered"


def test_the_pin_records_its_origin_date_corroborating_md5_and_reviewing_commit() -> None:
    """The committed pin is the trust root, and it says where, when and by whom (A.235)."""
    pin = load_pin()
    assert pin.archive_url == ARCHIVE_URL, pin
    assert {entry.name for entry in pin.files} == set(REQUIRED), pin
    assert date.fromisoformat(pin.first_fetched) <= date.today(), pin
    assert len(pin.md5_corroborated) == 32, pin
    assert len(pin.reviewed_commit) == 40, pin
