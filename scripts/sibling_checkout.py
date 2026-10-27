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

import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import Field

from command_outcome import announce
from contract_base import Contract, from_document
from gitenv import git, scrubbed_env
from rebase_state import ConflictReport, conflicts
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


# A.218: where sibling:trust records each review, read back by sibling:conclude.
TRUST_RECORDS = ROOT / ".artifacts" / "trust"


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
REFRESH_COMMAND = "sibling:refresh"
CONCLUDE_COMMAND = "sibling:conclude"
CONFLICTS_COMMAND = "sibling:conflicts"
TRUST_COMMAND = "sibling:trust"
PLAN_FILES = ("context/plan.toml", "context/plan-ids.toml", "context/plan-trace.toml")
MARKERS = ("<<<<<<< ", ">>>>>>> ")


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
    # THE CLONE'S OWN CONFIGS (A.208, A.215): under paranoid trust each file is trusted by
    # content, so a clone on another branch carries configs nobody trusted yet: its mise.toml,
    # and each tracked mise.<env>.toml that MISE_ENV selects. All are measured against the
    # commit the clone is at before any is trusted; an untracked one is never listed.
    tracked = git("ls-files", "-z", "--", "mise.*.toml", cwd=clone).stdout
    environments = sorted(
        name for name in tracked.split("\x00") if name and not name.endswith(".local.toml")
    )
    names = ("mise.toml", *environments)
    modified = [
        str(clone / name)
        for name in names
        if git("diff", "--quiet", "HEAD", "--", name, cwd=clone).returncode != 0
    ]
    if modified:
        raise SystemExit(
            f"{', '.join(modified)} differ from the commit the clone is at, so none is trusted: "
            "commit or discard those changes, then run sibling:override again"
        )
    for name in names:
        config = clone / name
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


def refresh(
    sibling: Sibling,
    parent: Path,
    step: str,
    ref: str | None = None,
    *,
    trust: Trust = _mise_trust,
) -> str:
    """A ref of the sibling's origin merged into the clone's feature branch by commit (A.209).

    LINEAGE IS NEVER REWRITTEN (A.191): a merge commit adds the integration. The merge is staged
    without committing; a merged mise.toml byte-identical to a reviewed commit, the clone's or
    the merged tip's, is trusted, and only then is the merge committed, so the clone's own hooks
    run against a trusted config (A.207, A.208). A conflict stops with its files named.
    """
    if not re.fullmatch(r"[A-Z]\.[0-9]+", step):
        raise SystemExit(f"refusing: {step!r} is not a plan step id, such as D.277")
    clone = parent / sibling.name
    if not (clone / ".git").exists():
        raise SystemExit(f"{clone} is not a clone yet; sibling:checkout makes it first")
    _verify_origin(clone, sibling)
    target = ref or sibling.branch
    with _non_interactive():
        fetched = git("fetch", "--quiet", "--prune", "origin", cwd=clone)
    if fetched.returncode != 0:
        raise SystemExit(f"{clone}: fetching origin failed: {fetched.stderr.strip()}")
    tip = git("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{target}", cwd=clone)
    if tip.returncode != 0:
        raise SystemExit(f"{sibling.source} has no branch {target!r}; nothing was merged")
    theirs = tip.stdout.strip()
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=clone).stdout.strip()
    if branch in {"", "develop", "main", sibling.branch}:
        where = branch or "a detached HEAD"
        raise SystemExit(f"{clone} is on {where}, not a feature branch; nothing was merged")
    if git("status", "--porcelain", "--untracked-files=no", cwd=clone).stdout.strip():
        raise SystemExit(f"{clone} has uncommitted changes; nothing was merged")
    before = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
    merged = git("merge", "--no-ff", "--no-commit", theirs, cwd=clone)
    if merged.returncode != 0:
        listed = git("diff", "--name-only", "--diff-filter=U", cwd=clone).stdout.split()
        named = ", ".join(listed) or "no file git named"
        # A STOPPED MERGE STAYS WORKABLE (A.212): the merge has already rewritten the clone's
        # files, so a mise.toml a reviewed commit holds is trusted before the conflict is
        # reported, and the clone's own tasks still run while it is resolved.
        _trust_reviewed(clone, (before, theirs), trust)
        raise SystemExit(
            f"merging origin/{target} into {clone} stopped on conflicts in {named}; "
            "nothing was committed"
        )
    if git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=clone).returncode == 0:
        config = clone / "mise.toml"
        reviewed = [
            git("diff", "--cached", "--quiet", commit, "--", "mise.toml", cwd=clone).returncode
            for commit in (before, theirs)
        ]
        if 0 not in reviewed:
            git("merge", "--abort", cwd=clone)
            raise SystemExit(
                f"{config} as merged matches neither {before[:12]} nor {theirs[:12]}, so it "
                "is not trusted; the merge was aborted and nothing was committed"
            )
        if trust(config) != 0:
            git("merge", "--abort", cwd=clone)
            raise SystemExit(f"mise trust {config} failed; the merge was aborted")
        message = (
            f"chore(merge): bring origin/{target} into {branch}\n\n"
            "A merge commit records the integration, so every commit the branch published "
            "keeps its hash (A.191, A.209).\n\n"
            f"Plan-Step: {step}"
        )
        committed = _commit_clean(clone, message)
        if committed.returncode != 0:
            raise SystemExit(
                f"the merge into {clone} was staged, but its commit was refused: "
                f"{(committed.stdout + committed.stderr).strip()}"
            )
    return git("rev-parse", "HEAD", cwd=clone).stdout.strip()


Resolve = Callable[[Path], int]


def _clone_resolver(clone: Path) -> int:
    """The clone's own plan-file resolver (cscie103 D.129), run in the cleaned environment."""
    command = ["uv", "run", "--no-sync", "python", "scripts/plan_conflicts.py"]
    env = setup_environment(os.environ)
    return subprocess.run(command, cwd=clone, env=env, check=False).returncode


def _unmerged_paths(clone: Path) -> list[str]:
    listed = git("diff", "--name-only", "-z", "--diff-filter=U", cwd=clone).stdout
    return [name for name in listed.split("\x00") if name]


def _trust_reviewed(clone: Path, commits: tuple[str, ...], trust: Trust) -> bool:
    """The clone's mise.toml trusted only when a reviewed commit holds it byte for byte (A.212)."""
    if "mise.toml" in _unmerged_paths(clone):
        return False
    reviewed = [
        git("diff", "--cached", "--quiet", commit, "--", "mise.toml", cwd=clone).returncode
        for commit in commits
    ]
    return 0 in reviewed and trust(clone / "mise.toml") == 0


def _stage_resolved(clone: Path, name: str) -> None:
    """A conflicted path resolved by hand, its file holding no marker, staged as D.31 does."""
    path = clone / name
    if not path.is_file():
        return
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not any(line.startswith(MARKERS) for line in lines):
        git("add", "--", name, cwd=clone)


def sibling_conflicts(sibling: Sibling, parent: Path) -> ConflictReport:
    """A sibling clone's stopped merge read as data, each conflicted file's blocks (A.212)."""
    clone = parent / sibling.name
    if not (clone / ".git").exists():
        raise SystemExit(f"{clone} is not a clone yet; sibling:checkout makes it first")
    _verify_origin(clone, sibling)
    return conflicts(clone)


def _marked(clone: Path) -> list[str]:
    """Staged files, changed against HEAD, that still hold a conflict block's opening or close."""
    changed = git("diff", "--cached", "--name-only", "-z", "HEAD", cwd=clone).stdout
    marked: list[str] = []
    for name in (entry for entry in changed.split("\x00") if entry):
        staged = git("show", f":{name}", cwd=clone)
        lines = staged.stdout.splitlines() if staged.returncode == 0 else []
        if any(line.startswith(MARKERS) for line in lines):
            marked.append(name)
    return marked


class _Review(Contract):
    """The review sibling:trust records: the config, the commit it was read at, its digest."""

    sibling: str
    config: str
    commit: str
    sha256: str


def _reviewed_merge(clone: Path, name: str, head: str) -> bool:
    """The merged mise.toml is the content its reviewer named against this HEAD (A.218)."""
    record = TRUST_RECORDS / f"{name}.json"
    if not record.is_file():
        return False
    named = from_document(_Review, json.loads(record.read_text(encoding="utf-8")))
    digest = hashlib.sha256((clone / "mise.toml").read_bytes()).hexdigest()
    observed = (named.sibling, named.config, named.commit, named.sha256)
    return observed == (name, "mise.toml", head, digest)


def conclude(
    sibling: Sibling,
    parent: Path,
    step: str,
    *,
    trust: Trust = _mise_trust,
    resolve: Resolve = _clone_resolver,
    include: tuple[str, ...] = (),
) -> str:
    """A sibling merge that stopped on conflicts, concluded by a commit naming the step (A.210).

    The clone's own resolver settles its plan files first. The merge is refused while a path
    stays unmerged or a staged file still holds a conflict marker, and its mise.toml is
    trusted only when byte-identical to a reviewed commit, as A.209 trusts it. Every refusal
    leaves the merge as it is, so no resolution already made is lost.
    """
    if not re.fullmatch(r"[A-Z]\.[0-9]+", step):
        raise SystemExit(f"refusing: {step!r} is not a plan step id, such as D.277")
    clone = parent / sibling.name
    if not (clone / ".git").exists():
        raise SystemExit(f"{clone} is not a clone yet; sibling:checkout makes it first")
    _verify_origin(clone, sibling)
    merging = git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=clone)
    if merging.returncode != 0:
        raise SystemExit(f"{clone} has no merge in progress, so there is nothing to conclude")
    theirs = merging.stdout.strip()
    head = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
    _trust_reviewed(clone, (head, theirs), trust)
    # A HAND RESOLUTION IS STAGED FIRST (A.216): the resolver reads the index stages, so it
    # would refuse a plan file already resolved in the working tree; only marked files reach it.
    for name in _unmerged_paths(clone):
        _stage_resolved(clone, name)
    if set(_unmerged_paths(clone)) & set(PLAN_FILES) and resolve(clone) != 0:
        raise SystemExit(f"the plan-file resolver in {clone} refused; nothing was committed")
    left = _unmerged_paths(clone)
    if left:
        raise SystemExit(
            f"{clone} still has unmerged paths: {', '.join(left)}; resolve and stage them, "
            "nothing was committed"
        )
    for name in include:
        _stage_included(clone, name)
    # NOTHING IS LEFT OUT (A.213): git commits only what is staged, so a tracked file edited
    # while resolving, but never staged, would be silently missing from the merge commit.
    unstaged = git("diff", "--name-only", "-z", cwd=clone).stdout
    left_out = [name for name in unstaged.split("\x00") if name]
    if left_out:
        raise SystemExit(
            f"{', '.join(left_out)} changed but unstaged in {clone}, so the merge commit would "
            "leave them out; stage or discard them, nothing was committed"
        )
    listed = git("ls-files", "--others", "--exclude-standard", "-z", cwd=clone).stdout
    untracked = [name for name in listed.split("\x00") if name]
    if untracked:
        raise SystemExit(
            f"{', '.join(untracked)} new in {clone} but not included, so the merge commit "
            "would leave them out; include or remove them, nothing was committed"
        )
    marked = _marked(clone)
    if marked:
        raise SystemExit(f"conflict markers remain in {', '.join(marked)}; nothing was committed")
    before = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
    config = clone / "mise.toml"
    reviewed = [
        git("diff", "--cached", "--quiet", commit, "--", "mise.toml", cwd=clone).returncode
        for commit in (before, theirs)
    ]
    if 0 not in reviewed and not _reviewed_merge(clone, sibling.name, before):
        raise SystemExit(
            f"{config} as merged matches neither {before[:12]} nor {theirs[:12]}, so it is "
            "not trusted, and no review names its digest; nothing was committed"
        )
    if trust(config) != 0:
        raise SystemExit(f"mise trust {config} failed; nothing was committed")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=clone).stdout.strip()
    message = (
        f"chore(merge): conclude the merge into {branch}\n\n"
        "The merge stopped on conflicts; they were resolved and staged before this commit "
        "(A.210).\n\n"
        f"Plan-Step: {step}"
    )
    committed = _commit_clean(clone, message)
    if committed.returncode != 0:
        raise SystemExit(
            f"the merge into {clone} was ready, but its commit was refused: "
            f"{(committed.stdout + committed.stderr).strip()}"
        )
    return git("rev-parse", "HEAD", cwd=clone).stdout.strip()


def _commit_clean(clone: Path, message: str) -> subprocess.CompletedProcess[str]:
    """A sibling merge commit in the cleaned environment: its hooks never see ours (A.214)."""
    return subprocess.run(
        ["git", "commit", "--quiet", "-m", message],
        cwd=clone,
        env=scrubbed_env(base=setup_environment(os.environ)),
        capture_output=True,
        text=True,
        check=False,
    )


def _stage_included(clone: Path, name: str) -> None:
    """A path the resolution names, modified, deleted or new, staged into the merge (A.214)."""
    if not (clone / name).resolve().is_relative_to(clone.resolve()):
        raise SystemExit(f"{name} lies outside {clone}; nothing was committed")
    if not git("status", "--porcelain", "--", name, cwd=clone).stdout.strip():
        raise SystemExit(f"{name} has no change in {clone} to include; nothing was committed")
    git("add", "-A", "--", name, cwd=clone)


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


def _conflicts_main(args: list[str]) -> int:
    """sibling:conflicts <name>, judged by the override policy first (A.212)."""
    known = {sibling.name: sibling for sibling in declared()}
    if len(args) != 1 or args[0] not in known:
        usage = f"usage: mise run run {CONFLICTS_COMMAND} <name>, one of {sorted(known)}"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, usage)
        return enforce(announce(CONFLICTS_COMMAND, stopped, "usage", usage, {}))
    sibling = known[args[0]]
    request = override_request(sibling, _siblings_parent())
    observed = request.model_dump(mode="json")
    judged = evaluate(request, OVERRIDE_SUBJECT, OVERRIDE_POLICY, OVERRIDE_ENTRYPOINT)
    verdict = decide(judged)
    if verdict.action != "proceed":
        code = refusal_code(verdict, "sibling_conflicts_refused")
        return enforce(announce(CONFLICTS_COMMAND, verdict, code, reasons(judged), observed))
    try:
        report = sibling_conflicts(sibling, _siblings_parent())
    except SystemExit as refused:
        reason = str(refused.code)
        stopped = halted(OVERRIDE_SUBJECT, OVERRIDE_ENTRYPOINT, OVERRIDE_POLICY, reason)
        refusal = "sibling_conflicts_refused"
        return enforce(announce(CONFLICTS_COMMAND, stopped, refusal, reason, observed))
    data = {**observed, "conflicts": report.model_dump(mode="json")}
    note = f"{sibling.name}: its stopped merge's conflicts, read as data"
    return enforce(announce(CONFLICTS_COMMAND, verdict, "sibling_conflicts_read", note, data))


def _conclude_main(args: list[str]) -> int:
    """sibling:conclude <name> <step>, judged by the override policy first (A.210)."""
    known = {sibling.name: sibling for sibling in declared()}
    rest = args[2:]
    pairs = len(rest) % 2 == 0 and all(flag == "--include" for flag in rest[::2])
    if len(args) < 2 or args[0] not in known or not pairs:
        usage = (
            f"usage: mise run run {CONCLUDE_COMMAND} <name> <step> [--include <path>]..., "
            f"one of {sorted(known)}"
        )
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, usage)
        return enforce(announce(CONCLUDE_COMMAND, stopped, "usage", usage, {}))
    sibling = known[args[0]]
    request = override_request(sibling, _siblings_parent())
    observed = request.model_dump(mode="json")
    judged = evaluate(request, OVERRIDE_SUBJECT, OVERRIDE_POLICY, OVERRIDE_ENTRYPOINT)
    verdict = decide(judged)
    if verdict.action != "proceed":
        code = refusal_code(verdict, "sibling_conclude_refused")
        return enforce(announce(CONCLUDE_COMMAND, verdict, code, reasons(judged), observed))
    try:
        after = conclude(sibling, _siblings_parent(), args[1], include=tuple(rest[1::2]))
    except SystemExit as refused:
        reason = str(refused.code)
        stopped = halted(OVERRIDE_SUBJECT, OVERRIDE_ENTRYPOINT, OVERRIDE_POLICY, reason)
        refusal = "sibling_conclude_refused"
        return enforce(announce(CONCLUDE_COMMAND, stopped, refusal, reason, observed))
    note = f"{sibling.name}: its merge concluded, now {after[:12]}"
    return enforce(announce(CONCLUDE_COMMAND, verdict, "sibling_concluded", note, observed))


def _refresh_main(args: list[str]) -> int:
    """sibling:refresh <name> <step> [ref], judged by the override policy first (A.209)."""
    known = {sibling.name: sibling for sibling in declared()}
    if len(args) not in (2, 3) or args[0] not in known:
        usage = f"usage: mise run run {REFRESH_COMMAND} <name> <step> [ref], one of {sorted(known)}"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, usage)
        return enforce(announce(REFRESH_COMMAND, stopped, "usage", usage, {}))
    sibling = known[args[0]]
    ref = args[2] if len(args) == 3 else None
    request = override_request(sibling, _siblings_parent())
    observed = request.model_dump(mode="json")
    judged = evaluate(request, OVERRIDE_SUBJECT, OVERRIDE_POLICY, OVERRIDE_ENTRYPOINT)
    verdict = decide(judged)
    if verdict.action != "proceed":
        code = refusal_code(verdict, "sibling_refresh_refused")
        return enforce(announce(REFRESH_COMMAND, verdict, code, reasons(judged), observed))
    try:
        after = refresh(sibling, _siblings_parent(), args[1], ref)
    except SystemExit as refused:
        reason = str(refused.code)
        stopped = halted(OVERRIDE_SUBJECT, OVERRIDE_ENTRYPOINT, OVERRIDE_POLICY, reason)
        refusal = "sibling_refresh_refused"
        return enforce(announce(REFRESH_COMMAND, stopped, refusal, reason, observed))
    merged = ref or sibling.branch
    note = f"{sibling.name}: origin/{merged} merged into its feature branch, now {after[:12]}"
    return enforce(announce(REFRESH_COMMAND, verdict, "sibling_refreshed", note, observed))


def review(
    sibling: Sibling, parent: Path, digest: str | None, *, trust: Trust = _mise_trust
) -> str:
    """Trust a sibling's edited mise.toml only at the digest its reviewer names (A.211).

    SHOWN, THEN NAMED. Content a commit holds needs no review: sibling:override trusts it.
    Edited content is refused with its diff against the commit and its sha256; the reviewer
    reads the change and names that digest, and only content still hashing to it is trusted.
    The decision is recorded under .artifacts/trust.
    """
    clone = parent / sibling.name
    if not (clone / ".git").exists():
        raise SystemExit(f"{clone} is not a clone yet; sibling:checkout makes it first")
    _verify_origin(clone, sibling)
    config = clone / "mise.toml"
    if git("diff", "--quiet", "HEAD", "--", "mise.toml", cwd=clone).returncode == 0:
        raise SystemExit(f"{config} is unmodified at its commit, so it needs no review")
    actual = hashlib.sha256(config.read_bytes()).hexdigest()
    if digest is None:
        change = git("diff", "HEAD", "--", "mise.toml", cwd=clone).stdout
        raise SystemExit(
            f"{config} differs from its commit; review the change, then name its digest:\n"
            f"{change}\nsha256 {actual}"
        )
    if digest != actual:
        raise SystemExit(f"{config} hashes to {actual}, not the digest {digest}; nothing trusted")
    if trust(config) != 0:
        raise SystemExit(f"mise trust {config} failed, so mise will not load it")
    head = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
    record = TRUST_RECORDS / f"{sibling.name}.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    decision = {"sibling": sibling.name, "config": "mise.toml", "commit": head, "sha256": actual}
    record.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    return f"{config} trusted at sha256 {actual}, reviewed against {head[:12]}"


def _trust_main(args: list[str]) -> int:
    """sibling:trust <name> [digest], judged by the override policy first (A.211)."""
    known = {sibling.name: sibling for sibling in declared()}
    if len(args) not in (1, 2) or args[0] not in known:
        usage = f"usage: mise run run {TRUST_COMMAND} <name> [digest], one of {sorted(known)}"
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, usage)
        return enforce(announce(TRUST_COMMAND, stopped, "usage", usage, {}))
    sibling = known[args[0]]
    digest = args[1] if len(args) == 2 else None
    request = override_request(sibling, _siblings_parent())
    observed = request.model_dump(mode="json")
    judged = evaluate(request, OVERRIDE_SUBJECT, OVERRIDE_POLICY, OVERRIDE_ENTRYPOINT)
    verdict = decide(judged)
    if verdict.action != "proceed":
        code = refusal_code(verdict, "sibling_trust_refused")
        return enforce(announce(TRUST_COMMAND, verdict, code, reasons(judged), observed))
    try:
        note = review(sibling, _siblings_parent(), digest)
    except SystemExit as refused:
        reason = str(refused.code)
        stopped = halted(OVERRIDE_SUBJECT, OVERRIDE_ENTRYPOINT, OVERRIDE_POLICY, reason)
        refusal = "sibling_trust_refused"
        return enforce(announce(TRUST_COMMAND, stopped, refusal, reason, observed))
    return enforce(announce(TRUST_COMMAND, verdict, "sibling_trusted", note, observed))


def main(argv: Sequence[str] | None = None) -> int:
    """sibling:checkout <name> -- clone, give a FAS mode, judge, then trust both files."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--conflicts"]:
        return _conflicts_main(args[1:])
    if args[:1] == ["--conclude"]:
        return _conclude_main(args[1:])
    if args[:1] == ["--refresh"]:
        return _refresh_main(args[1:])
    if args[:1] == ["--trust"]:
        return _trust_main(args[1:])
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
