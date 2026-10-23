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
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

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
    required: tuple[str, ...]
    files: tuple[DataFile, ...]


Download = Callable[[str, Path], None]


def _https_only() -> urllib.request.OpenerDirector:
    """An opener that speaks HTTPS alone: no file, ftp or plain-http handler is installed.

    urlopen's default opener also serves file: and ftp: URLs, which is why ruff's S310 flags
    every call to it. An OpenerDirector built from the HTTPS handler alone refuses any other
    scheme itself, a redirect to plain http included, so no suppression is needed (A.100).
    """
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.HTTPSHandler(),
        urllib.request.HTTPRedirectHandler(),
        urllib.request.HTTPErrorProcessor(),
        urllib.request.HTTPDefaultErrorHandler(),
    ):
        opener.add_handler(handler)
    return opener


def _download(url: str, target: Path) -> None:
    """The bytes at an https URL, written to target; every other scheme is refused."""
    if not url.startswith(SCHEME):
        raise SystemExit(f"data_fetch: refusing to download from {url}")
    with _https_only().open(url, timeout=120) as response:
        body: bytes = response.read()
    target.write_bytes(body)


def observe(
    archive_url: str,
    md5_url: str,
    staging: Path,
    download: Download = _download,
) -> DataFetch:
    """Download the archive and its MD5 into staging, and state what they hold."""
    staging.mkdir(parents=True, exist_ok=True)
    archive = staging / "archive.zip"
    sums = staging / "archive.zip.md5"
    download(archive_url, archive)
    download(md5_url, sums)
    data = archive.read_bytes()
    published = MD5.search(sums.read_text(encoding="utf-8", errors="replace").lower())
    files: list[DataFile] = []
    with zipfile.ZipFile(archive) as bundle:
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
        archive_sha256=hashlib.sha256(data).hexdigest(),
        required=REQUIRED,
        files=tuple(files),
    )


def fetch(
    archive_url: str,
    md5_url: str,
    destination: Path,
    download: Download = _download,
) -> tuple[DataFetch, list[str]]:
    """Observe, let runs.data_fetch decide, and unpack the required files only if it allows."""
    with tempfile.TemporaryDirectory() as scratch:
        staging = Path(scratch)
        record = observe(archive_url, md5_url, staging, download)
        found = spine.evaluate(record, SUBJECT, POLICY, ENTRYPOINT)
        refusals = sorted(rule.code for rule in found.rules if rule.outcome == "fail")
        if refusals:
            return record, refusals
        with zipfile.ZipFile(staging / "archive.zip") as bundle:
            for name in REQUIRED:
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                partial = target.with_name(target.name + ".partial")
                partial.write_bytes(bundle.read(name))
                os.replace(partial, target)
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
    data: dict[str, object] = {**record.model_dump(mode="json"), "destination": str(destination)}
    if refusals:
        return _announce("refused", "fetch_refused", ", ".join(refusals), data)
    message = f"{len(record.files)} files verified and unpacked into {destination}"
    return _announce("success", "fetched", message, data)


if __name__ == "__main__":
    sys.exit(main())
