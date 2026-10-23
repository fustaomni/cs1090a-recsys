"""Untracked copies of an upstream, verified against its pinned tree before removal (A.114).

OBSERVED, THEN JUDGED. Each untracked file in a named checkout is hashed as git hashes it, and
its blob id is set beside the blob at the same path in the upstream's tree at the pinned commit,
read from tree objects alone. The record holds observations only; runs.upstream_copies decides.

A MATCH IS RECOVERABLE. A copy whose blob equals the pinned blob is byte-identical to a file
that commit holds, so removing it loses nothing; --yes removes only those. Every other copy is
named by the policy and kept, since a changed file, or one the upstream never had, may be work
no commit holds. Without --yes nothing is removed. The checkout is named, not assumed, so this
runs from any worktree against another, such as a main checkout whose own tasks predate it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

import upstream
from contract_base import Contract
from gitenv import git
from spine import Verdict, evaluate

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "policies" / "runs" / "upstream_copies"
ENTRYPOINT = "data.runs.upstream_copies.deny"
SUBJECT = "upstream_copies"
USAGE = "usage: upstream_copies.py <checkout> <repository-url-or-path> <full-commit-sha> [--yes]"


class Copy(Contract):
    """One untracked file: its blob, and the pinned tree's blob at its path, if it has one."""

    path: str
    local_blob: str
    upstream_blob: str | None


class CopyInventory(Contract):
    """upstream-copies/v1: every untracked file in a checkout, set beside a pinned tree."""

    contract: Literal["upstream-copies/v1"] = "upstream-copies/v1"
    checkout: str
    source: str
    commit: str
    copies: tuple[Copy, ...]


def _untracked(checkout: Path) -> tuple[str, ...]:
    listed = git("ls-files", "--others", "--exclude-standard", "-z", cwd=checkout)
    if listed.returncode != 0:
        raise SystemExit(f"cannot list untracked files in {checkout}: {listed.stderr.strip()}")
    return tuple(sorted(path for path in listed.stdout.split("\0") if path))


def _blob(checkout: Path, path: str) -> str:
    hashed = git("hash-object", "--", path, cwd=checkout)
    if hashed.returncode != 0:
        raise SystemExit(f"cannot hash {path} in {checkout}: {hashed.stderr.strip()}")
    return hashed.stdout.strip()


def observe(
    checkout: Path, source: str, commit: str, root: Path = upstream.EVIDENCE
) -> CopyInventory:
    """The checkout's untracked files, each beside the pinned tree's blob at its path."""
    pinned = upstream.blobs(source, commit, root)
    copies = tuple(
        Copy(path=path, local_blob=_blob(checkout, path), upstream_blob=pinned.get(path))
        for path in _untracked(checkout)
    )
    return CopyInventory(checkout=str(checkout), source=source, commit=commit, copies=copies)


def judge(inventory: CopyInventory) -> Verdict:
    """runs.upstream_copies's verdict on the inventory."""
    return evaluate(inventory, SUBJECT, POLICY, ENTRYPOINT)


def main(argv: list[str] | None = None, *, root: Path = upstream.EVIDENCE) -> int:
    """upstream:copies <checkout> <source> <commit> [--yes]."""
    args = list(sys.argv[1:] if argv is None else argv)
    apply = "--yes" in args
    named = [arg for arg in args if arg != "--yes"]
    if len(named) != 3:
        raise SystemExit(f"{USAGE}  (got {args})")
    checkout, source, commit = Path(named[0]).resolve(), named[1], named[2]
    inventory = observe(checkout, source, commit, root)
    matching = [copy.path for copy in inventory.copies if copy.local_blob == copy.upstream_blob]
    if apply:
        for path in matching:
            (checkout / path).unlink()
        inventory = observe(checkout, source, commit, root)
    found = judge(inventory)
    kept = [line for rule in found.rules if rule.outcome == "fail" for line in rule.findings]
    report = {"removed" if apply else "would_remove": matching, "kept": kept}
    print(json.dumps(report, indent=2))
    return 1 if kept else 0


if __name__ == "__main__":
    raise SystemExit(main())
