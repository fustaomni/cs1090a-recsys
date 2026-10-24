"""Check out another repository at a pinned commit, read-only, as evidence (A.28).

READ AT A COMMIT, NEVER A BRANCH. A port reads its upstream at the exact commit it names: a
complete lowercase 40-character SHA, since an abbreviation is ambiguous and a branch moves. The
repository is cloned blobless into .artifacts/upstream/<name>-<sha12>-<source8>, named by a digest
of its normalized source so two sources sharing a name never share a clone, and an existing clone is
reused only once its origin reads back as that source (A.184), where evidence lives and
git does not look, checked out detached at that commit, and HEAD is verified to equal it. A
commit the repository does not hold is refused by name. Nothing in this repository changes, and
every Git call goes through gitenv's scrubbed environment.

ITS TREE IS LISTED AT THE SAME COMMIT (A.113). Given pathspecs, the checkout is verified exactly
as above, then every path under them in the tree at the commit, never HEAD, is listed from tree
objects alone, which the blobless clone already holds, so no blob is fetched. A pathspec is a
literal path, as git ls-tree reads it, so one matching nothing, a wildcard included, is refused
by name rather than vanishing from the answer (A.182).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

from gitenv import git, scrubbed_env

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / ".artifacts" / "upstream"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
USAGE = "usage: upstream.py <repository-url-or-path> <full-commit-sha> [pathspec...]"


def normalized(source: str) -> str:
    """A source as git records it, without a trailing slash or .git: one repository, one name."""
    return source.strip().rstrip("/").removesuffix(".git")


def location(source: str, commit: str, root: Path = EVIDENCE) -> Path:
    """Where source at commit lives: its name, the commit and a digest of the source (A.184)."""
    canonical = normalized(source)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
    return root / f"{Path(canonical).name}-{commit[:12]}-{digest}"


def checkout(source: str, commit: str, root: Path = EVIDENCE) -> Path:
    """The checkout of source at commit, created once and verified every time."""
    if not FULL_SHA.fullmatch(commit):
        raise SystemExit(f"{commit!r}: a pinned commit must be a full 40-character SHA")
    target = location(source, commit, root)
    if not target.exists():
        root.mkdir(parents=True, exist_ok=True)
        clone = ("clone", "--quiet", "--filter=blob:none", "--no-checkout", source, str(target))
        cloned = git(*clone, cwd=root)
        if cloned.returncode != 0:
            raise SystemExit(f"clone of {source} failed: {cloned.stderr.strip()}")
        detach = ("-c", "advice.detachedHead=false", "checkout", "--quiet", commit)
        checked = git(*detach, cwd=target)
        if checked.returncode != 0:
            raise SystemExit(f"{commit} is not in {source}: {checked.stderr.strip()}")
    origin = git("remote", "get-url", "origin", cwd=target)
    found = origin.stdout.strip() if origin.returncode == 0 else "no origin"
    if normalized(found) != normalized(source):
        raise SystemExit(f"{target} was cloned from {found}, not {source}; remove it")
    head = git("rev-parse", "HEAD", cwd=target)
    if head.returncode != 0 or head.stdout.strip() != commit:
        raise SystemExit(f"{target} is not at {commit}; remove it and check out again")
    return target


def _matches(pathspec: str, paths: tuple[str, ...]) -> bool:
    """A literal pathspec matches itself or anything beneath it; '.' matches anything (A.182)."""
    prefix = pathspec.rstrip("/")
    if prefix in ("", "."):
        return bool(paths)
    return any(path == prefix or path.startswith(f"{prefix}/") for path in paths)


def tree(
    source: str, commit: str, pathspecs: tuple[str, ...], root: Path = EVIDENCE
) -> tuple[str, ...]:
    """Every path under pathspecs at commit, the checkout verified first, from trees alone."""
    target = checkout(source, commit, root)
    listed = git("ls-tree", "-r", "-z", "--name-only", commit, "--", *pathspecs, cwd=target)
    if listed.returncode != 0:
        raise SystemExit(f"cannot list {commit} in {target}: {listed.stderr.strip()}")
    paths = tuple(sorted(path for path in listed.stdout.split("\0") if path))
    unmatched = [spec for spec in pathspecs if not _matches(spec, paths)]
    if unmatched:
        named = ", ".join(unmatched)
        raise SystemExit(f"{named}: nothing at {commit} matches; pathspecs are literal paths")
    return paths


def blobs(source: str, commit: str, root: Path = EVIDENCE) -> dict[str, str]:
    """Every file's blob id at commit, the checkout verified first, from trees alone (A.114)."""
    target = checkout(source, commit, root)
    listed = git("ls-tree", "-r", "-z", commit, cwd=target)
    if listed.returncode != 0:
        raise SystemExit(f"cannot list {commit} in {target}: {listed.stderr.strip()}")
    found: dict[str, str] = {}
    for record in listed.stdout.split("\0"):
        if record:
            meta, _, path = record.partition("\t")
            found[path] = meta.split()[2]
    return found


# NO TERMINAL, NO STDIN, A DEADLINE (A.204). gitenv.git scrubs routing variables only, so a
# remote that asks for credentials would prompt and an unanswering one would hang; these are
# the variables every recorded command here exports, and they belong in gitenv (A.150, A.197).
NON_INTERACTIVE = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS": "",
    "SSH_ASKPASS_REQUIRE": "never",
    "GCM_INTERACTIVE": "never",
    "GCM_GUI_PROMPT": "false",
}
TIP_SECONDS = 60


def tip(source: str, branch: str) -> str:
    """The full commit source's branch points at, by ls-remote, without cloning (A.204).

    A read is pinned to a commit, never a branch, so the branch is resolved first and the
    resolution is what the run records. ls-remote matches patterns, so its lines are kept only
    when the ref is exactly refs/heads/<branch>: a tag, or a longer branch ending in the same
    name, never passes. --exit-code tells a source without that branch (2) from one git could
    not read (any other failure). An option-shaped argument never reaches git.
    """
    for value in (source, branch):
        if value.startswith("-"):
            raise SystemExit(f"{value!r}: an option-shaped argument is refused")
    ref = f"refs/heads/{branch}"
    command = ["git", "ls-remote", "--exit-code", "--end-of-options", source, ref]
    try:
        done = subprocess.run(
            command,
            env=scrubbed_env() | NON_INTERACTIVE,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=TIP_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(f"{source} did not answer within {TIP_SECONDS}s") from None
    if done.returncode == 2:
        raise SystemExit(f"{source} has no branch {branch!r}")
    if done.returncode != 0:
        raise SystemExit(f"{source} cannot be read: {done.stderr.strip()}")
    exact = []
    for line in done.stdout.splitlines():
        commit, _, name = line.partition("\t")
        if name == ref:
            exact.append(commit)
    if len(exact) != 1 or not FULL_SHA.fullmatch(exact[0]):
        raise SystemExit(f"{source} gave no single commit for {ref}: {exact}")
    return exact[0]


def main() -> int:
    match sys.argv[1:]:
        case ["--tip", source, branch]:
            print(tip(source, branch))
            return 0
        case [source, commit]:
            print(checkout(source, commit))
            return 0
        case [source, commit, *pathspecs]:
            print("\n".join(tree(source, commit, tuple(pathspecs))))
            return 0
        case other:
            raise SystemExit(f"{USAGE}  (got {other})")


if __name__ == "__main__":
    raise SystemExit(main())
