# scripts/status_paths.py
"""status:paths -- every changed path a commit should name, derived rather than recalled (D.355).

PORTED FROM this repository's `commit paths` (RS.30), built after a commit's path list, composed
from memory, was wrong six times in one session. git's own record is read instead: porcelain v1,
NUL-separated, with every untracked file listed by its own path, because a wholly new directory
otherwise collapses to one entry and hides the file a commit is most likely to forget. The
records are parsed by repo_report.parse_porcelain, this hub's one reader of that format, which
already takes a rename's second record as its source rather than shifting by one.

BOTH SIDES OF A RENAME, UNLIKE UPSTREAM. recsys drops the source, since its commit stages with
git add. This hub's commit refuses a staged path it was not given (D.343), and a staged rename
stages the source's deletion, so the list a commit here must name holds both.

A GIT THAT CANNOT ANSWER IS NOT A CLEAN TREE. The observation records whether git answered, and
the spine refuses one that did not, rather than reporting nothing to name.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import JsonValue

from command_outcome import announce
from contract_base import Contract
from gitenv import git
from repo_report import parse_porcelain
from spine import decide, enforce, evaluate, reasons, refusal_code

ROOT = Path(__file__).resolve().parent.parent
COMMAND = "status:paths"
SUBJECT = "status_paths"
POLICY = ROOT / "policies" / "runs" / "status_paths"
ENTRYPOINT = "data.runs.status_paths.deny"


class StatusPaths(Contract):
    """status-paths/v1: whether git answered, and every path a commit should name (D.355)."""

    CONTRACT_ID: ClassVar[str] = "status-paths/v1"

    contract: Literal["status-paths/v1"] = "status-paths/v1"
    answered: bool
    detail: str
    paths: tuple[str, ...]


def named(raw: str) -> tuple[str, ...]:
    """Every path a commit must name: each change's path, and the source of each rename."""
    found: set[str] = set()
    for change in parse_porcelain(raw):
        found.add(change.path)
        if change.original_path is not None and change.status[0] == "R":
            found.add(change.original_path)
    return tuple(sorted(found))


def observe(root: Path) -> StatusPaths:
    """Ask git once for every change, each untracked file by its own path."""
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all", cwd=root)
    if status.returncode != 0:
        return StatusPaths(answered=False, detail=status.stderr.strip(), paths=())
    return StatusPaths(answered=True, detail="", paths=named(status.stdout))


def main(root: Path = ROOT) -> int:
    """Name every changed path, judged on the spine: the list is the message's data."""
    observed = observe(root)
    found = evaluate(observed, SUBJECT, POLICY, ENTRYPOINT)
    decision = decide(found)
    if decision.action != "proceed":
        code = refusal_code(decision, "status_paths_refused")
        return enforce(announce(COMMAND, decision, code, reasons(found), {}))
    data: dict[str, JsonValue] = {"paths": list(observed.paths)}
    message = f"{len(observed.paths)} path(s) a commit should name"
    return enforce(announce(COMMAND, decision, "paths_named", message, data))


if __name__ == "__main__":
    raise SystemExit(main())
