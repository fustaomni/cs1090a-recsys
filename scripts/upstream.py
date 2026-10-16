"""Check out another repository at a pinned commit, read-only, as evidence (A.28).

READ AT A COMMIT, NEVER A BRANCH. A port reads its upstream at the exact commit it names: a
complete lowercase 40-character SHA, since an abbreviation is ambiguous and a branch moves. The
repository is cloned blobless into .artifacts/upstream/<name>-<sha12>, where evidence lives and
git does not look, checked out detached at that commit, and HEAD is verified to equal it. A
commit the repository does not hold is refused by name. Nothing in this repository changes, and
every Git call goes through gitenv's scrubbed environment.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from gitenv import git

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / ".artifacts" / "upstream"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
USAGE = "usage: upstream.py <repository-url-or-path> <full-commit-sha>"


def checkout(source: str, commit: str, root: Path = EVIDENCE) -> Path:
    """The checkout of source at commit, created once and verified every time."""
    if not FULL_SHA.fullmatch(commit):
        raise SystemExit(f"{commit!r}: a pinned commit must be a full 40-character SHA")
    name = Path(source.rstrip("/")).name.removesuffix(".git")
    target = root / f"{name}-{commit[:12]}"
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
    head = git("rev-parse", "HEAD", cwd=target)
    if head.returncode != 0 or head.stdout.strip() != commit:
        raise SystemExit(f"{target} is not at {commit}; remove it and check out again")
    return target


def main() -> int:
    match sys.argv[1:]:
        case [source, commit]:
            print(checkout(source, commit))
            return 0
        case other:
            raise SystemExit(f"{USAGE}  (got {other})")


if __name__ == "__main__":
    raise SystemExit(main())
