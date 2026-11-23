# scripts/history_publish.py
"""history:publish -- a verified mirror replaces origin's history, leased and reversible (A.366).

GROUNDED. git push --force-with-lease=<ref>:<expect> overwrites a ref only while it still points
at <expect>, and --atomic makes every ref update together or none at all. history:rewrite
recorded each ref's tip before its first pass, since filter-repo rewrites its ref-map on every
pass; those recorded tips are the leases, so a ref anyone moved after the mirror was cut is
never overwritten. The plan is judged by runs.history_publish first: a moved ref, or nothing to
push, refuses the whole publish before anything changes.

A DRY RUN UNLESS --yes. Without it the plan is reported and nothing is pushed or lifted.

NEVER --mirror. Only the branches and tags the mirror holds are pushed, each named, so a ref
the mirror never had (a pull request's, an archive tag pushed since) is left as it is.

THE RULESET IS DISABLED ONLY FOR THE PUSH (A.369). develop and main also require a pull request
and a passing status check, and either refuses a direct push on its own, so removing single rules
never suffices: for the push the whole ruleset's enforcement is set to disabled, GitHub's own way
to suspend a ruleset without deleting it, and afterwards the ruleset is put back from
contracts/ruleset-develop-and-main.json, whether or not the push succeeded.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from command_outcome import announce
from contract_base import Contract, from_document
from gitenv import git
from history_rewrite import LEASES, RefLeases, tips
from library_errors import ToolFailedError
from spine import Decision, Verdict, decide, enforce, evaluate, halted, reasons

ROOT = Path(__file__).resolve().parent.parent
COMMAND = "history:publish"
SUBJECT = "history_publish"
POLICY = ROOT / "policies" / "runs" / "history_publish"
ENTRYPOINT = "data.runs.history_publish.deny"
RULESET = ROOT / "contracts" / "ruleset-develop-and-main.json"
LISTING = "repos/{owner}/{repo}/rulesets"
USAGE = "usage: mise run run history:publish <mirror> <remote> [--yes]"


class RefUpdate(Contract):
    ref: str
    old: str
    new: str


class PublishPlan(Contract):
    """history-publish-plan/v1: every ref the mirror would replace, any that has moved, and any
    branch or tag origin holds that the mirror lacks (A.368)."""

    contract: Literal["history-publish-plan/v1"] = "history-publish-plan/v1"
    mirror: str
    remote: str
    refs: list[RefUpdate]
    moved: list[str]
    uncovered: list[str] = Field(default_factory=list)


class PublishReport(Contract):
    """history-publish-report/v1: the judged plan, and what the publish did."""

    contract: Literal["history-publish-report/v1"] = "history-publish-report/v1"
    plan: PublishPlan
    execute: bool
    pushed: bool
    ruleset_restored: bool


class Remote(Protocol):
    url: str

    def tips(self) -> dict[str, str]: ...

    def push(self, updates: Sequence[RefUpdate]) -> bool: ...


class Ruleset(Protocol):
    def lift(self) -> bool: ...

    def restore(self) -> bool: ...


class PublishRefusedError(RuntimeError):
    """The plan was refused by runs.history_publish; nothing was lifted or pushed."""

    def __init__(self, message: str, decision: Decision) -> None:
        super().__init__(message)
        self.decision = decision


class PublishFailedError(RuntimeError):
    """The ruleset could not be lifted or restored; the message says which."""


class GitRemote:
    """A remote reached through gitenv: its tips by ls-remote, one atomic leased push."""

    def __init__(self, url: str, mirror: Path) -> None:
        self.url = url
        self.mirror = mirror

    def tips(self) -> dict[str, str]:
        listed = git("ls-remote", "--heads", "--tags", self.url, cwd=self.mirror)
        if listed.returncode != 0:
            raise ToolFailedError(
                listed.stderr.strip() or "git ls-remote failed",
                remediation="reach the remote: its URL must be readable with this key",
                tool="git ls-remote",
            )
        pairs = (line.split("\t", 1) for line in listed.stdout.splitlines() if "\t" in line)
        return {ref: sha for sha, ref in pairs if not ref.endswith("^{}")}

    def push(self, updates: Sequence[RefUpdate]) -> bool:
        leases = [f"--force-with-lease={update.ref}:{update.old}" for update in updates]
        refspecs = [f"{update.new}:{update.ref}" for update in updates]
        pushed = git(
            "push", "--atomic", "--porcelain", *leases, self.url, *refspecs, cwd=self.mirror
        )
        print((pushed.stdout + pushed.stderr).strip(), file=sys.stderr)
        return pushed.returncode == 0


class GhRuleset:
    """develop and main's ruleset on GitHub, put back from its contract (A.366)."""

    def __init__(self, contract: Path = RULESET) -> None:
        self.body = json.loads(contract.read_text(encoding="utf-8"))

    def _put(self, body: dict[str, object]) -> bool:
        environment = {**os.environ, "GH_PROMPT_DISABLED": "1"}
        listed = subprocess.run(
            ["gh", "api", LISTING],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
        )
        if listed.returncode != 0:
            return False
        found = [item["id"] for item in json.loads(listed.stdout) if item["name"] == body["name"]]
        if len(found) != 1:
            return False
        put = subprocess.run(
            ["gh", "api", "-X", "PUT", f"{LISTING}/{found[0]}", "--input", "-"],
            input=json.dumps(body),
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
            env=environment,
        )
        return put.returncode == 0

    def lift(self) -> bool:
        return self._put({**self.body, "enforcement": "disabled"})

    def restore(self) -> bool:
        return self._put(self.body)


def _judged(plan: PublishPlan) -> Verdict:
    """The plan judged by runs.history_publish: a moved ref or nothing to push refuses it."""
    return evaluate(plan, SUBJECT, POLICY, ENTRYPOINT)


def load_leases(mirror: Path) -> RefLeases:
    """The tips history:rewrite recorded when it cut this mirror."""
    document = json.loads((mirror / LEASES).read_text(encoding="utf-8"))
    return from_document(RefLeases, document)


def publish(mirror: Path, remote: Remote, ruleset: Ruleset, *, execute: bool) -> PublishReport:
    """Replace remote's branches and tags with the mirror's, each leased on its recorded tip."""
    leases = load_leases(mirror).refs
    local = tips(mirror)
    current = remote.tips()
    moved = sorted(ref for ref, old in leases.items() if current.get(ref) != old)
    # A REF ONLY ORIGIN HOLDS KEEPS ITS OLD HISTORY REACHABLE (A.368): it refuses the publish.
    uncovered = sorted(ref for ref in current if ref not in local)
    updates = [
        RefUpdate(ref=ref, old=leases[ref], new=new)
        for ref, new in sorted(local.items())
        if ref in leases
    ]
    plan = PublishPlan(
        mirror=str(mirror), remote=remote.url, refs=updates, moved=moved, uncovered=uncovered
    )
    found = _judged(plan)
    decision = decide(found)
    if decision.action != "proceed":
        raise PublishRefusedError(reasons(found), decision)
    if not execute:
        return PublishReport(plan=plan, execute=False, pushed=False, ruleset_restored=False)
    if not ruleset.lift():
        raise PublishFailedError("the ruleset was not disabled for the push")
    try:
        pushed = remote.push(updates)
    finally:
        restored = ruleset.restore()
    if not restored:
        raise PublishFailedError(f"the ruleset was not restored from {RULESET.name}; restore it")
    return PublishReport(plan=plan, execute=True, pushed=pushed, ruleset_restored=restored)


def main(argv: Sequence[str] | None = None) -> int:
    """history:publish <mirror> <remote> [--yes]: a dry run unless --yes."""
    args = list(sys.argv[1:] if argv is None else argv)
    execute = "--yes" in args
    named = [arg for arg in args if arg != "--yes"]
    if len(named) != 2:
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, USAGE)
        return enforce(announce(COMMAND, stopped, "usage", USAGE, {}))
    mirror = Path(named[0]).resolve()
    try:
        report = publish(mirror, GitRemote(named[1], mirror), GhRuleset(), execute=execute)
    except PublishRefusedError as refused:
        return enforce(announce(COMMAND, refused.decision, "publish_refused", str(refused), {}))
    except PublishFailedError as failed:
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, str(failed))
        return enforce(announce(COMMAND, stopped, "publish_failed", str(failed), {}))
    judged = decide(_judged(report.plan))
    data = report.model_dump(mode="json")
    count = len(report.plan.refs)
    if not execute:
        message = f"would replace {count} ref(s) on {report.plan.remote}; nothing pushed"
        return enforce(announce(COMMAND, judged, "publish_planned", message, data))
    if not report.pushed:
        reason = "the atomic push was refused; no ref changed, and the ruleset was restored"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, reason)
        return enforce(announce(COMMAND, stopped, "publish_refused_by_remote", reason, data))
    message = f"replaced {count} ref(s) on {report.plan.remote}; the ruleset was restored"
    return enforce(announce(COMMAND, judged, "history_published", message, data))


if __name__ == "__main__":
    raise SystemExit(main())
