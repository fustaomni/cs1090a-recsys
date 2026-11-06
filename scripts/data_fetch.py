"""data:fetch (A.100): MovieLens 1M, verified against its published MD5 before it is unpacked.

DATA IS VERIFIED BEFORE IT IS UNPACKED. The archive and its published MD5 are downloaded, the
archive's own MD5 and SHA-256 and every required file's SHA-256 are observed, runs.data_fetch
decides, and the files are extracted only when nothing is refused, so a replaced or corrupted
archive never reaches the data directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from http.client import HTTPMessage
from pathlib import Path, PurePosixPath
from typing import IO, Literal

from pydantic import Field

import spine
from command_outcome import CommandOutcome
from contract_base import Contract
from run_ledger import default_ledger

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "policies" / "runs" / "data_fetch"
ENTRYPOINT = "data.runs.data_fetch.deny"
SUBJECT = "data_fetch"
ARCHIVE_URL = "https://files.grouplens.org/datasets/movielens/ml-1m.zip"
MD5_URL = ARCHIVE_URL + ".md5"
REQUIRED = ("ml-1m/ratings.dat", "ml-1m/movies.dat", "ml-1m/users.dat")
SCHEME = "https://"
# Lookarounds over the hex class, not backslash escapes: no escape crosses a layer (M60).
MD5 = re.compile("(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")
MAX_MEMBER_BYTES = 64 * 1024 * 1024
# THE ARCHIVE'S BOUNDS (A.235): MovieLens 1M holds six entries and about 24 MB unpacked.
MAX_MEMBERS = 16
MAX_TOTAL_BYTES = 256 * 1024 * 1024
# EACH ATTEMPT HAS A DEADLINE, AND THE ATTEMPTS ARE BOUNDED (A.235): three attempts, the waits
# between them doubling from one second.
ATTEMPTS = 3
BACKOFF_SECONDS = 1.0
TIMEOUT_SECONDS = 120.0


class DataFile(Contract):
    """One file inside the archive, by its path there, with the SHA-256 of its bytes."""

    name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DataFetch(Contract):
    """data-fetch/v1: what one fetch downloaded, what was published for it, and what it holds."""

    contract: Literal["data-fetch/v1"] = "data-fetch/v1"
    archive_url: str = Field(min_length=1)
    md5_published: str | None
    md5_observed: str = Field(pattern=r"^[0-9a-f]{32}$")
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_pinned: str = Field(pattern=r"^[0-9a-f]{64}$")
    unsafe: tuple[str, ...]
    member_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    max_members: int = Field(ge=1)
    max_total_bytes: int = Field(ge=1)
    required: tuple[str, ...]
    files: tuple[DataFile, ...]


class DataPin(Contract):
    """data-pin/v1: the reviewed bytes data:fetch trusts, and how they came to be trusted (A.235).

    The trust root is archive_sha256, committed and reviewed; md5_corroborated is the publisher's
    MD5 it was checked against, which guards only against accidental corruption.
    """

    contract: Literal["data-pin/v1"] = "data-pin/v1"
    archive_url: str = Field(pattern=r"^https://")
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: tuple[DataFile, ...] = Field(min_length=1)
    first_fetched: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    md5_corroborated: str = Field(pattern=r"^[0-9a-f]{32}$")
    reviewed_commit: str = Field(pattern=r"^[0-9a-f]{40}$")


PIN = ROOT / "contracts" / "data-pin.toml"


def load_pin(path: Path = PIN) -> DataPin:
    """The committed pin, validated through its contract as JSON so arrays read as tuples."""
    return DataPin.model_validate_json(json.dumps(tomllib.loads(path.read_text(encoding="utf-8"))))


Download = Callable[[str, Path], None]


def _unsafe(info: zipfile.ZipInfo) -> bool:
    """A member that is absolute, climbs out, names a drive, or is not a plain file or folder."""
    name = info.filename
    kind = stat.S_IFMT(info.external_attr >> 16)
    return (
        name.startswith("/")
        or "\\" in name
        or (len(name) > 1 and name[1] == ":")
        or ".." in PurePosixPath(name).parts
        or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
    )


def _origin(url: str) -> tuple[str, str]:
    """A URL's origin as its scheme and host, lowercased; an explicit port is part of the host."""
    parts = urllib.parse.urlsplit(url)
    return parts.scheme.lower(), parts.netloc.lower()


class SameOriginRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect handler that follows a redirect only within ARCHIVE_URL's origin (A.235).

    urllib follows a 3xx without re-checking the first URL's scheme or host, so a redirect could
    downgrade to plain HTTP or move to another host. A target outside the origin is refused as the
    HTTPError urllib raises for an unhandled redirect.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        if _origin(newurl) != _origin(ARCHIVE_URL):
            reason = f"redirect to {newurl} refused: only {ARCHIVE_URL}'s origin is fetched from"
            raise urllib.error.HTTPError(req.full_url, code, reason, headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _https_only() -> urllib.request.OpenerDirector:
    """An opener that speaks HTTPS alone: no file, ftp or plain-http handler is installed.

    urlopen's default opener also serves file: and ftp: URLs, which is why ruff's S310 flags
    every call to it. An OpenerDirector built from the HTTPS handler alone refuses any other
    scheme itself, a redirect to plain http included, so no suppression is needed (A.100).
    """
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.HTTPSHandler(),
        SameOriginRedirects(),
        urllib.request.HTTPErrorProcessor(),
        urllib.request.HTTPDefaultErrorHandler(),
    ):
        opener.add_handler(handler)
    return opener


Read = Callable[[str, float], bytes]


def _read(url: str, timeout: float) -> bytes:
    """One attempt: the whole body at url, through the HTTPS-only, same-origin opener."""
    with _https_only().open(url, timeout=timeout) as response:
        body: bytes = response.read()
    return body


def _download(
    url: str, target: Path, *, read: Read = _read, sleep: Callable[[float], None] = time.sleep
) -> None:
    """The bytes at an allow-listed URL, written to target; every other origin is refused."""
    if _origin(url) != _origin(ARCHIVE_URL):
        raise SystemExit(f"data_fetch: refusing to download from {url}")
    delay = BACKOFF_SECONDS
    for attempt in range(1, ATTEMPTS + 1):
        try:
            body = read(url, TIMEOUT_SECONDS)
        except OSError as error:
            if attempt == ATTEMPTS:
                reason = f"data_fetch: gave up on {url} after {ATTEMPTS} attempts: {error}"
                raise SystemExit(reason) from error
            sleep(delay)
            delay *= 2
        else:
            target.write_bytes(body)
            return


def observe(
    archive_url: str,
    md5_url: str,
    staging: Path,
    download: Download = _download,
    pin: DataPin | None = None,
) -> DataFetch:
    """Download the archive and its MD5 into staging, and state what they hold.

    PINNED BEFORE IT IS OPENED (A.235): the archive is digested as bytes first, and opened as a
    zip only when that digest is its reviewed pin, so an archive the pin does not name lists no
    files and is never parsed. The decision is runs.data_fetch's; this only observes.
    """
    pinned = pin or load_pin()
    staging.mkdir(parents=True, exist_ok=True)
    archive = staging / "archive.zip"
    sums = staging / "archive.zip.md5"
    download(archive_url, archive)
    download(md5_url, sums)
    data = archive.read_bytes()
    archive_sha256 = hashlib.sha256(data).hexdigest()
    published = MD5.search(sums.read_text(encoding="utf-8", errors="replace").lower())
    files: list[DataFile] = []
    unsafe: list[str] = []
    member_count = 0
    total_bytes = 0
    if archive_sha256 == pinned.archive_sha256:
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.infolist()
            member_count = len(members)
            total_bytes = sum(info.file_size for info in members)
            unsafe = [info.filename for info in members if _unsafe(info)]
            present = set(bundle.namelist())
            for name in REQUIRED:
                if name not in present or bundle.getinfo(name).file_size > MAX_MEMBER_BYTES:
                    continue
                digest = hashlib.sha256(bundle.read(name)).hexdigest()
                files.append(DataFile(name=name, sha256=digest))
    return DataFetch(
        archive_url=archive_url,
        md5_published=published.group(0) if published else None,
        md5_observed=hashlib.md5(data, usedforsecurity=False).hexdigest(),
        archive_sha256=archive_sha256,
        archive_pinned=pinned.archive_sha256,
        unsafe=tuple(unsafe),
        member_count=member_count,
        total_bytes=total_bytes,
        max_members=MAX_MEMBERS,
        max_total_bytes=MAX_TOTAL_BYTES,
        required=REQUIRED,
        files=tuple(files),
    )


def _published(destination: Path, pin: DataPin) -> bool:
    """Every required file is published, and its bytes are the ones its pin names (A.235)."""
    pinned = {entry.name: entry.sha256 for entry in pin.files}
    for name in REQUIRED:
        target = destination / name
        if not target.is_file():
            return False
        if hashlib.sha256(target.read_bytes()).hexdigest() != pinned.get(name):
            return False
    return True


def _publish(fresh: Path, destination: Path) -> None:
    """Swap a complete staging directory into place by rename, on the same filesystem (A.235)."""
    if not destination.exists():
        os.replace(fresh, destination)
        return
    retired = destination.with_name(f".{destination.name}.retired")
    shutil.rmtree(retired, ignore_errors=True)
    os.replace(destination, retired)
    os.replace(fresh, destination)
    shutil.rmtree(retired)


def fetch(
    archive_url: str,
    md5_url: str,
    destination: Path,
    download: Download = _download,
    pin: DataPin | None = None,
) -> tuple[DataFetch | None, list[str]]:
    """Observe, let runs.data_fetch decide, and publish the required files only if it allows.

    A VERIFIED COPY IS NOT FETCHED AGAIN: when every published file matches its pin there is no
    record and nothing to refuse. Otherwise the members are written into a fresh directory beside
    the destination and published with one rename, so an interruption publishes nothing.
    """
    pinned = pin or load_pin()
    if _published(destination, pinned):
        return None, []
    with tempfile.TemporaryDirectory() as scratch:
        staging = Path(scratch)
        record = observe(archive_url, md5_url, staging, download, pinned)
        found = spine.evaluate(record, SUBJECT, POLICY, ENTRYPOINT)
        refusals = sorted(rule.code for rule in found.rules if rule.outcome == "fail")
        if refusals:
            return record, refusals
        destination.parent.mkdir(parents=True, exist_ok=True)
        fresh = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
        try:
            with zipfile.ZipFile(staging / "archive.zip") as bundle:
                for name in REQUIRED:
                    target = fresh / name
                    if not target.resolve().is_relative_to(fresh.resolve()):
                        raise SystemExit(f"data_fetch: refusing to write {name} outside {fresh}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(bundle.read(name))
            _publish(fresh, destination)
        finally:
            shutil.rmtree(fresh, ignore_errors=True)
    return record, []


def _announce(outcome: str, code: str, message: str, data: dict[str, object]) -> int:
    envelope = CommandOutcome.model_validate(
        {
            "command": "data:fetch",
            "outcome": outcome,
            "code": code,
            "message": message,
            "data": data,
        }
    )
    print(json.dumps(envelope.model_dump(), indent=2))
    return envelope.exit_code


def main() -> int:
    destination = default_ledger().parent.parent / "data"
    record, refusals = fetch(ARCHIVE_URL, MD5_URL, destination)
    if record is None:
        message = f"every file in {destination} matches its reviewed pin; nothing was fetched"
        return _announce("success", "already_verified", message, {"destination": str(destination)})
    data: dict[str, object] = {**record.model_dump(mode="json"), "destination": str(destination)}
    if refusals:
        return _announce("refused", "fetch_refused", ", ".join(refusals), data)
    message = f"{len(record.files)} files verified and unpacked into {destination}"
    return _announce("success", "fetched", message, data)


if __name__ == "__main__":
    sys.exit(main())
