# scripts/history_rewrite.py
"""history:rewrite -- history rewritten from rules given as data, into a separate mirror (A.364).

GROUNDED. git-filter-repo is driven as a library (RepoFilter with Python callbacks), pinned
exactly because its own documentation asks callers of the library to keep one version. It works
on a fresh clone, removes the origin remote after a rewrite and keeps a cumulative commit-map,
original id to current id, across runs in the same repository.

THE RULES ARE DATA, NEVER COMMITTED. history-rewrite/v1 names the message lines to drop, the
text to replace in messages and files, and the paths whose commit citations are remapped. The
task reads them from stdin and never echoes them: its outcome carries counts only.

NOTHING IS PUSHED. The source is cloned bare into a path that must not exist yet, so the source
stays the backup; every pass runs in that mirror. Commit ids cited in files change as their
commits are rewritten, and rewriting a cited file changes ids again, so citation passes repeat
until one changes nothing. The result is verified and judged by runs.history_verify.

The library starts git itself, outside gitenv, so it runs with gitenv's scrubbed environment
and from the mirror as its working directory: an inherited GIT_DIR cannot redirect it.
"""

from __future__ import annotations

import contextlib
import os
import re
import sys
import tomllib
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Literal, Protocol

import git_filter_repo as fr
from pydantic import ValidationError

from command_outcome import announce
from contract_base import Contract
from gitenv import git, scrubbed_env
from library_errors import ToolFailedError
from spine import Decision, decide, enforce, evaluate, halted, reasons, schema_verdict

ROOT = Path(__file__).resolve().parent.parent
COMMAND = "history:rewrite"
SUBJECT = "history_rewrite"
POLICY = ROOT / "policies" / "runs" / "history_rewrite"
ENTRYPOINT = "data.runs.history_rewrite.deny"
VERIFY_SUBJECT = "history_verify"
VERIFY_POLICY = ROOT / "policies" / "runs" / "history_verify"
VERIFY_ENTRYPOINT = "data.runs.history_verify.deny"
USAGE = "usage: mise run run history:rewrite <source> <mirror>, history-rewrite/v1 on stdin"
MAX_PASSES = 30
HASH = re.compile(rb"\b[0-9a-f]{7,40}\b")
ABSENT = "0" * 40
LEASES = "history-leases.json"


class Replacement(Contract):
    find: str
    replace: str


class RewriteRules(Contract):
    """history-rewrite/v1: what the rewrite changes, given at run time and never committed."""

    contract: Literal["history-rewrite/v1"] = "history-rewrite/v1"
    drop_lines: list[str]
    replace_text: list[Replacement]
    cited_paths: list[str]


class RewritePlan(Contract):
    """history-rewrite-plan/v1: what a rewrite would do, observed before anything is cloned."""

    contract: Literal["history-rewrite-plan/v1"] = "history-rewrite-plan/v1"
    source: str
    mirror: str
    mirror_exists: bool
    rules: int


class RefLeases(Contract):
    """history-leases/v1: each branch and tag's tip as the source held it when the mirror was cut.

    history:publish leases every push on these, so a ref that moved since is never overwritten.
    filter-repo rewrites its own ref-map on every pass, so the tips are read before the first.
    """

    contract: Literal["history-leases/v1"] = "history-leases/v1"
    source: str
    refs: dict[str, str]


class RewriteReport(Contract):
    """history-rewrite-report/v1: the mirror as verified after the last pass."""

    contract: Literal["history-rewrite-report/v1"] = "history-rewrite-report/v1"
    mirror: str
    commits: int
    rewritten: dict[str, str]
    citation_passes: int
    citations_remapped: int
    stale_citations: int
    remaining_matches: int
    remotes: int


class _FileInfo(Protocol):
    """The helper filter-repo hands a file_info_callback: blobs read and written by id."""

    def get_contents_by_identifier(self, blob_id: bytes) -> bytes: ...

    def insert_file_with_contents(self, contents: bytes) -> bytes: ...


class RewriteRefusedError(RuntimeError):
    """The plan was refused by runs.history_rewrite; nothing was cloned or written."""

    def __init__(self, message: str, decision: Decision) -> None:
        super().__init__(message)
        self.decision = decision


class RewriteFailedError(RuntimeError):
    """The citations did not settle within MAX_PASSES; the mirror is left for inspection."""


@contextlib.contextmanager
def _scrubbed(mirror: Path) -> Iterator[None]:
    """The library's git children inherit no routing variable and resolve from the mirror."""
    saved = dict(os.environ)
    scrubbed = scrubbed_env(base=saved)
    os.environ.clear()
    os.environ.update(scrubbed)
    try:
        with contextlib.chdir(mirror):
            yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _filter(mirror: Path, *, force: bool, **callbacks: Callable[..., object]) -> None:
    args = fr.FilteringOptions.default_options()
    args.force = force
    args.quiet = True
    args.replace_refs = "delete-no-add"
    with _scrubbed(mirror):
        fr.RepoFilter(args, **callbacks).run()


def _git(mirror: Path, *argv: str) -> str:
    done = git(*argv, cwd=mirror)
    if done.returncode != 0:
        raise ToolFailedError(
            done.stderr.strip() or f"git {argv[0]} failed",
            remediation="read the rewritten mirror: a git command on it failed",
            tool=f"git {argv[0]}",
        )
    return done.stdout


def tips(repository: Path) -> dict[str, str]:
    """Every branch and tag in repository, each to the object its ref names."""
    listed = _git(repository, "for-each-ref", "--format=%(objectname) %(refname)", "refs/heads")
    tagged = _git(repository, "for-each-ref", "--format=%(objectname) %(refname)", "refs/tags")
    lines = (listed + tagged).splitlines()
    return {ref: sha for sha, ref in (line.split(" ", 1) for line in lines if line.strip())}


def _commit_map(mirror: Path) -> dict[str, str]:
    """filter-repo's cumulative commit-map: each original id to its current id."""
    metadata = Path(_git(mirror, "rev-parse", "--absolute-git-dir").strip()) / "filter-repo"
    lines = (metadata / "commit-map").read_text(encoding="utf-8").splitlines()[1:]
    pairs = (line.split() for line in lines if line.strip())
    return {old: new for old, new in pairs if new != ABSENT}


def _drop(rules: RewriteRules) -> Callable[[bytes], bytes]:
    patterns = [re.compile(pattern) for pattern in rules.drop_lines]

    def message(text: bytes) -> bytes:
        decoded = text.decode("utf-8", "surrogateescape")
        for item in rules.replace_text:
            decoded = decoded.replace(item.find, item.replace)
        kept = [
            line
            for line in decoded.split("\n")
            if not any(pattern.search(line) for pattern in patterns)
        ]
        return ("\n".join(kept).rstrip("\n") + "\n").encode("utf-8", "surrogateescape")

    return message


def _replace(rules: RewriteRules) -> Callable[[fr.Blob, object], None]:
    pairs = [(item.find.encode(), item.replace.encode()) for item in rules.replace_text]

    def blob(found: fr.Blob, _metadata: object) -> None:
        for old, new in pairs:
            found.data = found.data.replace(old, new)

    return blob


def _remapper(stale: dict[str, str]) -> Callable[[re.Match[bytes]], bytes]:
    """A cited id, full or abbreviated, replaced by the same length of its current id."""
    by_prefix: dict[str, list[str]] = {}
    for old in stale:
        by_prefix.setdefault(old[:7], []).append(old)

    def remap(match: re.Match[bytes]) -> bytes:
        token = match.group(0).decode()
        found = [old for old in by_prefix.get(token[:7], []) if old.startswith(token)]
        if len(found) != 1:
            return match.group(0)
        return stale[found[0]][: len(token)].encode()

    return remap


def _citation_pass(mirror: Path, cited: frozenset[bytes], stale: dict[str, str]) -> int:
    remap = _remapper(stale)
    changed = 0

    def info(filename: bytes, mode: bytes, blob_id: bytes, value: _FileInfo) -> tuple[bytes, ...]:
        nonlocal changed
        if filename not in cited:
            return (filename, mode, blob_id)
        contents = value.get_contents_by_identifier(blob_id)
        updated = HASH.sub(remap, contents)
        if updated == contents:
            return (filename, mode, blob_id)
        changed += 1
        return (filename, mode, value.insert_file_with_contents(updated))

    _filter(mirror, force=True, file_info_callback=info)
    return changed


def _stale(lineage: dict[str, set[str]], current: dict[str, str]) -> dict[str, str]:
    """Every id a commit has had, other than its current one, to that current id."""
    return {
        earlier: current[original]
        for original, ids in lineage.items()
        for earlier in ids
        if earlier != current[original]
    }


def _verify(mirror: Path, rules: RewriteRules, stale: dict[str, str]) -> tuple[int, int]:
    """Matches the rules still find, and cited ids that still name a rewritten commit."""
    patterns = [re.compile(pattern) for pattern in rules.drop_lines]
    messages = _git(mirror, "log", "--all", "--format=%B%x00").split("\0")
    remaining = sum(
        1
        for message in messages
        for line in message.split("\n")
        if any(pattern.search(line) for pattern in patterns)
    )
    for item in rules.replace_text:
        remaining += sum(item.find in message for message in messages)
        introduced = _git(mirror, "log", "--all", "--format=%H", f"-S{item.find}")
        remaining += len(introduced.split())
    if not rules.cited_paths or not stale:
        return remaining, 0
    shown = _git(mirror, "log", "--all", "--format=", "-p", "--", *rules.cited_paths)
    remap = _remapper(stale)
    tokens = HASH.findall(shown.encode())
    return remaining, sum(1 for token in tokens if HASH.sub(remap, token) != token)


def rewrite(source: str, mirror: Path, rules: RewriteRules) -> RewriteReport:
    """Clone source bare into mirror, rewrite it there by rules, and report what verification found.

    The plan is judged by runs.history_rewrite first: a mirror path that already exists, or
    rules that change nothing, is refused before anything is cloned. Nothing is ever pushed.
    """
    count = len(rules.drop_lines) + len(rules.replace_text) + len(rules.cited_paths)
    plan = RewritePlan(
        source=source, mirror=str(mirror), mirror_exists=mirror.exists(), rules=count
    )
    found = evaluate(plan, SUBJECT, POLICY, ENTRYPOINT)
    decision = decide(found)
    if decision.action != "proceed":
        raise RewriteRefusedError(reasons(found), decision)
    cloned = git("clone", "--bare", "--no-local", "--quiet", source, str(mirror))
    if cloned.returncode != 0:
        raise ToolFailedError(
            cloned.stderr.strip() or "git clone failed",
            remediation="clone the source: its URL or path must be readable",
            tool="git clone",
        )
    leases = RefLeases(source=source, refs=tips(mirror))
    _filter(mirror, force=False, message_callback=_drop(rules), blob_callback=_replace(rules))
    (mirror / LEASES).write_text(leases.model_dump_json(indent=2), encoding="utf-8")
    current = _commit_map(mirror)
    lineage = {original: {original, now} for original, now in current.items()}
    cited = frozenset(path.encode() for path in rules.cited_paths)
    passes = remapped = 0
    while cited:
        if passes == MAX_PASSES:
            raise RewriteFailedError(f"citations did not settle in {MAX_PASSES} passes in {mirror}")
        changed = _citation_pass(mirror, cited, _stale(lineage, current))
        passes += 1
        remapped += changed
        current = _commit_map(mirror)
        for original, now in current.items():
            lineage[original].add(now)
        if changed == 0:
            break
    remaining, stale_citations = _verify(mirror, rules, _stale(lineage, current))
    return RewriteReport(
        mirror=str(mirror),
        commits=len(current),
        rewritten=current,
        citation_passes=passes,
        citations_remapped=remapped,
        stale_citations=stale_citations,
        remaining_matches=remaining,
        remotes=len(_git(mirror, "remote").split()),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """history:rewrite <source> <mirror>, its rules as history-rewrite/v1 TOML on stdin."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, USAGE)
        return enforce(announce(COMMAND, stopped, "usage", USAGE, {}))
    source, mirror = args[0], Path(args[1]).resolve()
    try:
        rules = RewriteRules.model_validate(tomllib.loads(sys.stdin.read()))
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        refused = decide(schema_verdict(SUBJECT, RewriteRules, str(error)))
        return enforce(announce(COMMAND, refused, "rules_invalid", "rules failed their schema", {}))
    try:
        report = rewrite(source, mirror, rules)
    except RewriteRefusedError as refused:
        return enforce(announce(COMMAND, refused.decision, "rewrite_refused", str(refused), {}))
    verdict = evaluate(report, VERIFY_SUBJECT, VERIFY_POLICY, VERIFY_ENTRYPOINT)
    decision = decide(verdict)
    summary = report.model_dump(mode="json", exclude={"rewritten"})
    if decision.action != "proceed":
        return enforce(announce(COMMAND, decision, "rewrite_unverified", reasons(verdict), summary))
    message = f"{report.commits} commit(s) rewritten into {mirror}; nothing pushed"
    return enforce(announce(COMMAND, decision, "history_rewritten", message, summary))


if __name__ == "__main__":
    raise SystemExit(main())
