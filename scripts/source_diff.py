# scripts/source_diff.py
"""source:diff -- a worktree's uncommitted changes as data, before any is discarded (D.476).

GROUNDED. Tracked changes come from `git diff HEAD` through gitenv's scrubbed environment and
are parsed by python-unidiff into files, hunks and the lines each adds and removes. Untracked
paths come from `git ls-files --others --exclude-standard` and are named with their size from
stat: they are never opened, so nothing in them reaches the report. A git call that fails raises
a typed error; it is never read as an empty diff. The read is announced on the spine, judged
against its own schema, as worktree:conflicts is.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from unidiff.patch import Hunk, PatchedFile, PatchSet

from command_outcome import announce
from contract_base import Contract
from gitenv import git
from library_errors import ToolFailedError
from spine import decide, enforce, halted, schema_verdict

ROOT = Path(__file__).resolve().parent.parent
SUBJECT = "source_diff"
POLICY = ROOT / "policies" / "runs" / "source_diff"
ENTRYPOINT = "data.runs.source_diff.deny"
USAGE = "usage: mise run run source:diff <slug>"
Status = Literal["added", "modified", "removed", "renamed"]


class DiffHunk(Contract):
    source_start: int
    source_length: int
    target_start: int
    target_length: int
    added: int
    removed: int


class ChangedFile(Contract):
    path: str
    status: Status
    hunks: tuple[DiffHunk, ...]


class Untracked(Contract):
    path: str
    size: int


class DiffReport(Contract):
    """source-diff/v1: what a worktree changed since HEAD, and what it holds untracked."""

    contract: Literal["source-diff/v1"] = "source-diff/v1"
    files: tuple[ChangedFile, ...]
    untracked: tuple[Untracked, ...]


def _status(patched: PatchedFile) -> Status:
    if patched.is_added_file:
        return "added"
    if patched.is_removed_file:
        return "removed"
    if patched.is_rename:
        return "renamed"
    return "modified"


def _hunk(hunk: Hunk) -> DiffHunk:
    return DiffHunk(
        source_start=hunk.source_start,
        source_length=hunk.source_length,
        target_start=hunk.target_start,
        target_length=hunk.target_length,
        added=hunk.added,
        removed=hunk.removed,
    )


def diff(path: Path) -> DiffReport:
    """Every tracked change since HEAD in the worktree at path, and every untracked path by size."""
    shown = git("diff", "--no-color", "--no-ext-diff", "HEAD", cwd=path)
    if shown.returncode != 0:
        raise ToolFailedError(
            shown.stderr.strip() or "git diff failed",
            remediation="read a git worktree: git diff HEAD could not report its changes",
            tool="git diff",
        )
    files = tuple(
        ChangedFile(
            path=patched.path,
            status=_status(patched),
            hunks=tuple(_hunk(hunk) for hunk in patched),
        )
        for patched in PatchSet(shown.stdout)
    )
    listed = git("ls-files", "--others", "--exclude-standard", "-z", cwd=path)
    if listed.returncode != 0:
        raise ToolFailedError(
            listed.stderr.strip() or "git ls-files failed",
            remediation="read a git worktree: git ls-files could not list its untracked paths",
            tool="git ls-files",
        )
    names = sorted(name for name in listed.stdout.split("\0") if name)
    untracked = tuple(Untracked(path=name, size=(path / name).stat().st_size) for name in names)
    return DiffReport(files=files, untracked=untracked)


def main(argv: Sequence[str] | None = None) -> int:
    """source:diff <slug>: the uncommitted changes in the worktree the slug names."""
    from worktree import sibling_path

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, USAGE)
        return enforce(announce("source:diff", stopped, "usage", USAGE, {}))
    path = sibling_path(args[0])
    if not path.exists():
        reason = f"{path} does not exist"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, reason)
        return enforce(announce("source:diff", stopped, "worktree_missing", reason, {}))
    report = diff(path)
    read = decide(schema_verdict(SUBJECT, DiffReport, None))
    message = f"{len(report.files)} changed file(s), {len(report.untracked)} untracked"
    data = report.model_dump(mode="json")
    return enforce(announce("source:diff", read, "diff_read", message, data))


if __name__ == "__main__":
    raise SystemExit(main())
