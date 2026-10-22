# scripts/sibling_checkout.py
"""sibling:checkout -- a declared sibling, cloned with a FAS mode, trusted as merged (A.185).

cscie103-data-engineering, the reference every sibling ports from, runs every task inside nix
develop, which FAS OnDemand cannot run. This clones a sibling contracts/siblings.toml declares,
beside this repository's main checkout, from its canonical source over HTTPS with prompts off;
an existing clone is reused only once its origin reads back as that source (A.184). It writes a
mise.local.toml replacing the Nix shell with bash and pinning the declared tools, kept out of the
tree through .git/info/exclude. Trust is by provenance, since the founding policy describes this
repository alone: the sibling's mise.toml unmodified at a commit on its develop, and the override
exactly as declared, judged by policies/runs/sibling_trust before mise trusts either file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import Field

from command_outcome import announce
from contract_base import Contract, from_document
from gitenv import git
from setup_env import setup_environment
from spine import decide, enforce, evaluate, halted, reasons, refusal_code
from template_new import _non_interactive
from upstream import normalized

ROOT = Path(__file__).resolve().parent.parent
COMMAND = "sibling:checkout"
SUBJECT = "sibling_trust"
POLICY = ROOT / "policies" / "runs" / "sibling_trust"
ENTRYPOINT = "data.runs.sibling_trust.deny"
DECLARATION = Path("contracts") / "siblings.toml"
OVERRIDE = "mise.local.toml"


class Sibling(Contract):
    """One declared sibling: its name, its canonical source, and its FAS mode's tools."""

    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    branch: str = Field(default="develop", min_length=1)
    tools: dict[str, str]


class _Siblings(Contract):
    contract: Literal["siblings/v1"]
    siblings: tuple[Sibling, ...]


class SiblingTrust(Contract):
    """sibling-trust/v1: what was observed of a sibling's configuration before trusting it."""

    contract: Literal["sibling-trust/v1"] = "sibling-trust/v1"
    name: str
    head_on_develop: bool
    config_unmodified: bool
    override_matches: bool


def declared(root: Path = ROOT) -> tuple[Sibling, ...]:
    """Every sibling contracts/siblings.toml declares."""
    text = (root / DECLARATION).read_text(encoding="utf-8")
    return from_document(_Siblings, tomllib.loads(text)).siblings


def checkout(sibling: Sibling, parent: Path) -> Path:
    """The sibling's clone under parent, made once over HTTPS, its origin verified every time."""
    target = parent / sibling.name
    if not target.exists():
        parent.mkdir(parents=True, exist_ok=True)
        with _non_interactive():
            command = ("clone", "--quiet", "--branch", sibling.branch, sibling.source, str(target))
            cloned = git(*command, cwd=parent)
        if cloned.returncode != 0:
            raise SystemExit(f"clone of {sibling.source} failed: {cloned.stderr.strip()}")
    origin = git("remote", "get-url", "origin", cwd=target)
    found = origin.stdout.strip() if origin.returncode == 0 else "no origin"
    if normalized(found) != normalized(sibling.source):
        raise SystemExit(f"{target} was cloned from {found}, not {sibling.source}; remove it")
    _onto_branch(target, sibling)
    return target


def _onto_branch(clone: Path, sibling: Sibling) -> None:
    """The clone on its declared branch at the remote tip: switched, fast-forwarded, only clean."""
    with _non_interactive():
        fetched = git("fetch", "--quiet", "origin", cwd=clone)
    if fetched.returncode != 0:
        raise SystemExit(f"{clone}: fetching origin failed: {fetched.stderr.strip()}")
    dirty = git("status", "--porcelain", "--untracked-files=no", cwd=clone).stdout.strip()
    if dirty:
        raise SystemExit(f"{clone} has uncommitted changes; it is neither switched nor merged")
    current = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=clone).stdout.strip()
    if current != sibling.branch:
        switched = git("switch", "--quiet", sibling.branch, cwd=clone)
        if switched.returncode != 0:
            reason = f"{clone}: cannot switch to {sibling.branch}: {switched.stderr.strip()}"
            raise SystemExit(reason)
    tip = f"origin/{sibling.branch}"
    merged = git("merge", "--ff-only", "--quiet", tip, cwd=clone)
    if merged.returncode != 0:
        raise SystemExit(f"{clone}: {sibling.branch} cannot fast-forward to {tip}; nothing changed")


def override_text(sibling: Sibling) -> str:
    """The FAS mode: bash in place of nix develop, and exactly the declared tools."""
    pins = [
        f"{json.dumps(name)} = {json.dumps(sibling.tools[name])}" for name in sorted(sibling.tools)
    ]
    lines = [
        "# mise.local.toml, written by sibling:checkout (A.185): this checkout's FAS mode.",
        "# Never committed: .git/info/exclude keeps it out of the tree.",
        "[task_config]",
        'shell = "bash -c"',
        "",
        "[tools]",
        *pins,
    ]
    return "\n".join(lines) + "\n"


def write_override(clone: Path, sibling: Sibling) -> Path:
    """Write the override whole and exclude it locally, so the tree stays clean."""
    written = clone / OVERRIDE
    written.write_text(override_text(sibling), encoding="utf-8")
    located = git("rev-parse", "--git-path", "info/exclude", cwd=clone)
    if located.returncode != 0:
        raise SystemExit(f"{clone} has no git directory to exclude from: {located.stderr.strip()}")
    exclude = clone / located.stdout.strip()
    exclude.parent.mkdir(parents=True, exist_ok=True)
    present = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if OVERRIDE not in present.splitlines():
        separator = "" if present == "" or present.endswith("\n") else "\n"
        exclude.write_text(f"{present}{separator}{OVERRIDE}\n", encoding="utf-8")
    return written


def observe(clone: Path, sibling: Sibling) -> SiblingTrust:
    """What trusting needs: HEAD on origin/develop, mise.toml unmodified, the override exact."""
    with _non_interactive():
        fetched = git("fetch", "--quiet", "origin", cwd=clone)
    head = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
    tip = git("rev-parse", f"origin/{sibling.branch}", cwd=clone)
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=clone).stdout.strip()
    at_tip = tip.returncode == 0 and head == tip.stdout.strip() and branch == sibling.branch
    unmodified = git("diff", "--quiet", "HEAD", "--", "mise.toml", cwd=clone)
    override = clone / OVERRIDE
    return SiblingTrust(
        name=sibling.name,
        head_on_develop=fetched.returncode == 0 and at_tip,
        config_unmodified=unmodified.returncode == 0,
        override_matches=override.is_file()
        and override.read_text(encoding="utf-8") == override_text(sibling),
    )


Setup = Callable[..., int]


def _run_setup(command: list[str], *, cwd: Path, env: dict[str, str]) -> int:
    return subprocess.run(command, cwd=cwd, env=env, check=False).returncode


def set_up(
    clone: Path, *, run: Setup = _run_setup, environ: Mapping[str, str] | None = None
) -> None:
    """Run the sibling's own setup, cleaned of the caller's VIRTUAL_ENV, as worktree:add does."""
    env = setup_environment(os.environ if environ is None else environ)
    if run(["mise", "run", "setup"], cwd=clone, env=env) != 0:
        raise SystemExit(f"{clone}: its setup task failed, so it is not workable")


def _siblings_parent() -> Path:
    """Where siblings live: beside this repository's main checkout, never inside a worktree."""
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=ROOT)
    if common.returncode != 0:
        raise SystemExit(f"cannot find this repository's main checkout: {common.stderr.strip()}")
    return Path(common.stdout.strip()).parent.parent


def main(argv: Sequence[str] | None = None) -> int:
    """sibling:checkout <name> -- clone, give a FAS mode, judge, then trust both files."""
    args = list(sys.argv[1:] if argv is None else argv)
    known = {sibling.name: sibling for sibling in declared()}
    if len(args) != 1 or args[0] not in known:
        usage = f"usage: mise run run sibling:checkout <name>, one of {sorted(known)}"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, usage)
        return enforce(announce(COMMAND, stopped, "usage", usage, {}))
    sibling = known[args[0]]
    clone = checkout(sibling, _siblings_parent())
    write_override(clone, sibling)
    evidence = observe(clone, sibling)
    data = evidence.model_dump(mode="json")
    found = evaluate(evidence, SUBJECT, POLICY, ENTRYPOINT)
    decision = decide(found)
    if decision.action != "proceed":
        code = refusal_code(decision, "sibling_untrusted")
        return enforce(announce(COMMAND, decision, code, reasons(found), data))
    for name in ("mise.toml", OVERRIDE):
        trusted = subprocess.run(
            ["mise", "trust", str(clone / name)], capture_output=True, text=True, check=False
        )
        if trusted.returncode != 0:
            reason = f"mise trust {name} failed: {trusted.stderr.strip()}"
            stopped = halted(SUBJECT, ENTRYPOINT, POLICY, reason)
            return enforce(announce(COMMAND, stopped, "sibling_untrusted", reason, data))
    set_up(clone)
    message = f"{sibling.name} at {clone}: cloned, given its FAS mode, trusted and set up"
    return enforce(announce(COMMAND, decision, "sibling_checked_out", message, data))


if __name__ == "__main__":
    raise SystemExit(main())
