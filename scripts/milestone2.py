# scripts/milestone2.py
"""Milestone 2's walking skeleton: one number from a verified archive to the proposal (A.244).

The slice is the production pipe at its thinnest: the archive is verified against its pinned
SHA-256, the notebook counts its ratings, the count is recorded in a results contract with its
provenance, and one line of the proposal is rendered from that record alone. Each lane-two step
widens a stage here rather than replacing it.
"""

from __future__ import annotations

import hashlib
import runpy
import tempfile
import zipfile
from pathlib import Path
from typing import Literal

from pydantic import Field

from contract_base import Contract
from data_fetch import REQUIRED
from model_run import canonical

DIGEST = r"^[0-9a-f]{64}$"
# THE MEMBER data:fetch REQUIRES, never retyped: the skeleton reads what A.235 will fetch.
RATINGS = next(name for name in REQUIRED if name.endswith("/ratings.dat"))


class ArchiveRefusedError(Exception):
    """The archive is not the one its pin names, so nothing downstream may read it."""


class NotebookIncompleteError(Exception):
    """The notebook ran but left no integer ratings_count, so there is nothing to record."""


class Results(Contract):
    """milestone2-results/v1: what the notebook found, and the exact bytes it found it in."""

    contract: Literal["milestone2-results/v1"] = "milestone2-results/v1"
    ratings: int = Field(ge=0)
    archive_sha256: str = Field(pattern=DIGEST)
    notebook: str = Field(min_length=1)
    notebook_sha256: str = Field(pattern=DIGEST)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_archive(archive: Path, pinned: str) -> str:
    """The archive's SHA-256 when it is the pinned one; ArchiveRefusedError otherwise."""
    observed = _sha256(archive)
    if observed != pinned:
        raise ArchiveRefusedError(f"{archive.name} has SHA-256 {observed}, not the pinned {pinned}")
    return observed


def run_notebook(notebook: Path, archive: Path, pinned: str, out: Path) -> Results:
    """Verify the archive, run the notebook on it, and record what it found at out.

    VERIFIED BEFORE IT IS READ: a refused archive raises before any member is opened, so no
    results file is written for bytes the pin does not name.
    """
    digest = verify_archive(archive, pinned)
    with tempfile.TemporaryDirectory() as scratch:
        ratings = Path(scratch) / Path(RATINGS).name
        with zipfile.ZipFile(archive) as bundle:
            ratings.write_bytes(bundle.read(RATINGS))
        found: dict[str, object] = runpy.run_path(str(notebook), init_globals={"RATINGS": ratings})
    count = found.get("ratings_count")
    if not isinstance(count, int) or isinstance(count, bool):
        raise NotebookIncompleteError(f"{notebook.name} left no integer ratings_count")
    results = Results(
        ratings=count,
        archive_sha256=digest,
        notebook=notebook.name,
        notebook_sha256=_sha256(notebook),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(canonical(results.model_dump(mode="json")))
    return results


def render_line(results: Results) -> str:
    """The proposal's line for the ratings count, carrying the archive digest it traces to."""
    traced = results.archive_sha256[:12]
    return f"MovieLens 1M holds {results.ratings:,} ratings [archive sha256:{traced}]."
