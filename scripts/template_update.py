# scripts/template_update.py
"""A generated project takes a later commit of this template, pinned, on a branch (A.134).

cscie103's pipeline built every precondition for copier update -- an HTTPS source recorded as
_src_path, a full sha as _commit, a clean repository as the diff baseline -- and stopped short
of the operation. Here it is, in that pipeline's shape: Python observes, and
policies/runs/template/update decides. A bare copier update has destroyed the project it was
upgrading in 2026 practice, so the ref is a full sha, the tree clean, the branch a feature
branch, and the source this template. Copier's API requires overwrite=True for an update; a
conflict is left as a .rej file and reported by path, never as success.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar, Literal

import yaml
from copier import run_update

from command_outcome import announce
from contract_base import Contract
from gitenv import git
from project_identity import load
from spine import decide, enforce, evaluate, halted, reasons, refusal_code
from template_new import _non_interactive

ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = "data.runs.template.update.deny"
COMMAND = "template:update"
SUBJECT = "template_update"
POLICY = ROOT / "policies" / "runs" / "template" / "update"
ANSWERS = ".copier-answers.yml"


class UpdateRequest(Contract):
    """template-update/v1: a generated project, the template it records, and the ref wanted."""

    CONTRACT_ID: ClassVar[str] = "template-update/v1"

    contract: Literal["template-update/v1"] = "template-update/v1"
    destination: str
    answers_present: bool
    source: str | None
    template: str
    recorded: str | None
    ref: str
    branch: str
    clean: bool


def _answers(target: Path) -> dict[str, object]:
    """The answers Copier recorded, or none when the file is absent or not a mapping."""
    path = target / ANSWERS
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def request(destination: Path, ref: str, *, root: Path = ROOT) -> UpdateRequest:
    """The request as observed: what was generated, from where, and the tree it would change."""
    target = destination.expanduser().resolve()
    answers = _answers(target)
    branch, clean = "", False
    # ONLY ITS OWN REPOSITORY: without .git, git would answer for an enclosing one.
    if (target / ".git").exists():
        branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=target).stdout.strip()
        status = git("status", "--porcelain", cwd=target)
        clean = status.returncode == 0 and not status.stdout.strip()
    return UpdateRequest(
        destination=str(target),
        answers_present=bool(answers),
        source=_text(answers.get("_src_path")),
        template=f"{load(root).repository}.git",
        recorded=_text(answers.get("_commit")),
        ref=ref,
        branch=branch,
        clean=clean,
    )


def _rejects(target: Path) -> list[str]:
    """Every .rej file Copier left: a hunk of the template's change it could not apply."""
    listed = git("ls-files", "--others", "--exclude-standard", "--", "*.rej", cwd=target)
    return sorted(line for line in listed.stdout.splitlines() if line)


def main(argv: Sequence[str] | None = None) -> int:
    """template:update <destination> <ref> -- update, pinned, or refuse with every reason."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        usage = "usage: mise run run template:update <destination> <ref>"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, usage)
        return enforce(announce(COMMAND, stopped, "usage", usage, {}))
    made = request(Path(args[0]), args[1])
    observed = made.model_dump(mode="json")
    found = evaluate(made, SUBJECT, POLICY, ENTRYPOINT)
    decision = decide(found)
    if decision.action != "proceed":
        code = refusal_code(decision, "template_update_refused")
        return enforce(announce(COMMAND, decision, code, reasons(found), observed))
    # REACHED ONLY WHEN THE POLICY ALLOWS: generated, this template, a full sha, clean, a branch.
    target = Path(made.destination)
    try:
        with _non_interactive():
            run_update(
                made.destination,
                vcs_ref=made.ref,
                defaults=True,
                overwrite=True,
                conflict="rej",
                quiet=True,
            )
    except Exception as problem:
        reason = (str(problem).strip() or type(problem).__name__).splitlines()[0]
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, reason)
        return enforce(announce(COMMAND, stopped, "update_failed", reason, observed))
    rejects = _rejects(target)
    if rejects:
        reason = f"{len(rejects)} hunk file(s) left to resolve: {', '.join(rejects)}"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, reason)
        data = {**observed, "rejects": rejects}
        return enforce(announce(COMMAND, stopped, "update_conflicted", reason, data))
    recorded = _text(_answers(target).get("_commit"))
    if recorded is None or not made.ref.startswith(recorded):
        reason = f"{ANSWERS} records {recorded}, not {made.ref}"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, reason)
        return enforce(announce(COMMAND, stopped, "update_unrecorded", reason, observed))
    message = f"{made.destination}: from {made.recorded} to {made.ref}"
    return enforce(announce(COMMAND, decision, "project_updated", message, observed))


if __name__ == "__main__":
    sys.exit(main())
