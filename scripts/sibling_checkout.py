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
    # WHERE THE TOOLCHAIN COMES FROM (A.188): the nixpkgs revision the sibling's flake.lock pins,
    # and each tool's nixpkgs file, so every pin is proven to be the version the flake resolves.
    nixpkgs: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    packages: dict[str, str] = Field(default_factory=dict)


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
    # A.188: the clone's flake.lock still pins the nixpkgs the FAS mode's versions were read at.
    toolchain_current: bool


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
    _verify_origin(target, sibling)
    _onto_branch(target, sibling)
    return target


def _verify_origin(target: Path, sibling: Sibling) -> None:
    """The clone's origin reads back as the declared source, or it is refused, named (A.184)."""
    origin = git("remote", "get-url", "origin", cwd=target)
    found = origin.stdout.strip() if origin.returncode == 0 else "no origin"
    if normalized(found) != normalized(sibling.source):
        raise SystemExit(f"{target} was cloned from {found}, not {sibling.source}; remove it")


OVERRIDE_COMMAND = "sibling:override"
OVERRIDE_SUBJECT = "sibling_override"
OVERRIDE_POLICY = ROOT / "policies" / "runs" / "sibling_override"
OVERRIDE_ENTRYPOINT = "data.runs.sibling_override.deny"


class SiblingOverride(Contract):
    """sibling-override/v1: what was observed of a clone before its FAS mode is rewritten."""

    contract: Literal["sibling-override/v1"] = "sibling-override/v1"
    name: str
    clone: str
    clone_exists: bool
    origin: str
    origin_matches: bool


def override_request(sibling: Sibling, parent: Path) -> SiblingOverride:
    """The clone as observed: whether it exists, and where its origin points (A.189)."""
    target = parent / sibling.name
    exists = (target / ".git").exists()
    found = "no clone"
    if exists:
        origin = git("remote", "get-url", "origin", cwd=target)
        found = origin.stdout.strip() if origin.returncode == 0 else "no origin"
    return SiblingOverride(
        name=sibling.name,
        clone=str(target),
        clone_exists=exists,
        origin=found,
        origin_matches=exists and normalized(found) == normalized(sibling.source),
    )


Trust = Callable[[Path], int]


def _mise_trust(path: Path) -> int:
    """Under paranoid, trust is content-bound: a rewritten file is trusted again, by its path."""
    done = subprocess.run(["mise", "trust", str(path)], capture_output=True, text=True, check=False)
    return done.returncode


def _write_and_trust(clone: Path, sibling: Sibling, trust: Trust) -> Path:
    """Write and trust the FAS mode, then the clone's own mise.toml once unmodified (A.208)."""
    written = write_override(clone, sibling)
    if trust(written) != 0:
        raise SystemExit(f"mise trust {written} failed, so mise will not load it")
    # THE CLONE'S OWN CONFIG (A.208): under paranoid trust each file is trusted by content,
    # so a clone on another branch carries a mise.toml nobody trusted yet. It is measured as
    # sibling:checkout measures it, and trusted only unmodified at the commit it is at.
    config = clone / "mise.toml"
    if git("diff", "--quiet", "HEAD", "--", "mise.toml", cwd=clone).returncode != 0:
        raise SystemExit(
            f"{config} differs from the commit the clone is at, so it is not trusted: "
            "commit or discard that change, then run sibling:override again"
        )
    if trust(config) != 0:
        raise SystemExit(f"mise trust {config} failed, so mise will not load it")
    return written


def refresh_override(sibling: Sibling, parent: Path, *, trust: Trust = _mise_trust) -> Path:
    """The declared FAS mode, written into a clone on whatever branch it is, judged, trusted."""
    request = override_request(sibling, parent)
    found = evaluate(request, OVERRIDE_SUBJECT, OVERRIDE_POLICY, OVERRIDE_ENTRYPOINT)
    if decide(found).action != "proceed":
        raise SystemExit(reasons(found))
    return _write_and_trust(Path(request.clone), sibling, trust)


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


def _locked_nixpkgs(clone: Path) -> str | None:
    """The nixpkgs revision the clone's flake.lock pins, or None when it pins none (A.188)."""
    lock = clone / "flake.lock"
    if not lock.is_file():
        return None
    try:
        rev = json.loads(lock.read_text(encoding="utf-8"))["nodes"]["nixpkgs"]["locked"]["rev"]
    except (ValueError, KeyError, TypeError):
        return None
    return str(rev)


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
    locked = _locked_nixpkgs(clone)
    return SiblingTrust(
        name=sibling.name,
        head_on_develop=fetched.returncode == 0 and at_tip,
        config_unmodified=unmodified.returncode == 0,
        override_matches=override.is_file()
        and override.read_text(encoding="utf-8") == override_text(sibling),
        toolchain_current=sibling.nixpkgs is None or locked == sibling.nixpkgs,
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
    override_only = args[:1] == ["--override"]
    args = args[1:] if override_only else args
    known = {sibling.name: sibling for sibling in declared()}
    if len(args) != 1 or args[0] not in known:
        command = OVERRIDE_COMMAND if override_only else COMMAND
        usage = f"usage: mise run run {command} <name>, one of {sorted(known)}"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, usage)
        return enforce(announce(command, stopped, "usage", usage, {}))
    sibling = known[args[0]]
    if override_only:
        request = override_request(sibling, _siblings_parent())
        observed = request.model_dump(mode="json")
        judged = evaluate(request, OVERRIDE_SUBJECT, OVERRIDE_POLICY, OVERRIDE_ENTRYPOINT)
        verdict = decide(judged)
        if verdict.action != "proceed":
            code = refusal_code(verdict, "sibling_override_refused")
            return enforce(announce(OVERRIDE_COMMAND, verdict, code, reasons(judged), observed))
        try:
            written = _write_and_trust(Path(request.clone), sibling, _mise_trust)
        except SystemExit as refused:
            reason = str(refused.code)
            stopped = halted(OVERRIDE_SUBJECT, OVERRIDE_ENTRYPOINT, OVERRIDE_POLICY, reason)
            untrusted = "sibling_override_untrusted"
            return enforce(announce(OVERRIDE_COMMAND, stopped, untrusted, reason, observed))
        note = f"{written}: the declared FAS mode, written and trusted on the clone's branch"
        written_code = "sibling_override_written"
        return enforce(announce(OVERRIDE_COMMAND, verdict, written_code, note, observed))
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
