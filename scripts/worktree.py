"""Manage linked worktrees: add, list, remove.

WHY A SCRIPT AND NOT `git worktree add` TYPED BY HAND
Every project operation is a mise task. A hand-typed worktree leaves no record
of where worktrees go, what they are named, or what setup they need -- and the
setup is what bites, because git copies none of it.

WHAT GIT DOES NOT COPY, AND WHY add RUNS setup
A fresh worktree has no .venv, an untrusted mise.toml, and no installed git
hooks, so `mise run check` cannot run in it and neither can a commit. The
guidance is to "script the setup that git doesn't copy"; here that is
`mise run setup`, which already owns exactly those three things.

LAYOUT: SIBLING DIRECTORIES, NAMED AFTER THE BRANCH
The dominant convention, because it avoids nested .git problems and makes active
work visible from one `ls`. Branch slashes do not translate to folder names, so
feature/workstation-as-code becomes <repo>-workstation-as-code.

REMOVAL IS DELIBERATELY UNFORGIVING
`git worktree remove` refuses on modified or untracked files, and --force is "a
good way to lose a .env you copied in" -- so --force is never passed. `git branch
-d` refuses unmerged work, which makes it double as proof the merge happened.
Neither is a limitation to route around; both are the check.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import machine_trust
from gitenv import git as git_run
from gitenv import git_bytes
from setup_env import setup_environment

# TWO PARENTS, NOT THREE. This file moved from scripts/git/worktree.py to
# scripts/worktree.py, and the depth moved with it. Three levels reached
# ~/ltphongssvn -- not a git repository -- and every command failed with
# "fatal: not a git repository". A path computed by counting is a path that
# breaks when a file moves.
ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str, cwd: Path | None = None) -> str:
    # SCRUBBED ENVIRONMENT, NOT bare subprocess.run. GIT_DIR and friends are
    # exported into every hook and OVERRIDE cwd, so a git call made from a hook
    # operates on the hook's repository no matter where it was pointed. This is
    # worktree plumbing; being silently redirected to a different worktree is
    # precisely the failure it must not have.
    result = git_run(*args, cwd=cwd or ROOT)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(f"git {' '.join(args)} failed")
    return result.stdout


def parse_worktrees() -> list[dict[str, str]]:
    """Parse `git worktree list --porcelain -z`, failing closed.

    -z IS NOT OPTIONAL. `worktree list --porcelain` does NOT quote paths, so a
    path containing a newline silently corrupts a line-based parser -- and the
    git docs recommend combining --porcelain with -z for exactly this reason.

    FAIL CLOSED: an unrecognised record shape refuses the whole inventory rather
    than returning a partial one. Destructive verbs sit on this parser, and
    acting on a half-understood list is how the wrong directory gets removed.
    """
    raw = git_bytes("worktree", "list", "--porcelain", "-z", cwd=ROOT)
    if raw.returncode != 0:
        print(raw.stderr.decode(errors="replace").strip(), file=sys.stderr)
        raise SystemExit("git worktree list failed")

    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for token in raw.stdout.split(b"\0"):
        if token == b"":
            # An empty token closes a record.
            if current:
                worktrees.append(current)
                current = {}
            continue

        try:
            text = token.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SystemExit(f"worktree path is not UTF-8: {error}") from error

        key, _, value = text.partition(" ")
        if key not in {"worktree", "HEAD", "branch", "bare", "detached", "locked", "prunable"}:
            raise SystemExit(f"unrecognised worktree attribute {key!r}; refusing to continue")
        current[key] = value

    if current:
        worktrees.append(current)

    if not worktrees or "worktree" not in worktrees[0]:
        raise SystemExit("no main worktree reported; is this a git repository?")
    if "bare" in worktrees[0]:
        raise SystemExit(
            "the main worktree is bare. The sibling layout composes paths from a "
            "parent checkout, and a bare repository has none."
        )

    return worktrees


def sibling_path(slug: str) -> Path:
    main = Path(parse_worktrees()[0]["worktree"])
    return main.parent / f"{main.name}-{slug}"


def cmd_add(slug: str, base: str | None = None) -> int:
    """A new feature branch in a sibling worktree, cut from a named base or a fresh develop.

    THE BASE IS EXPLICIT FIRST (A.93): a stale or hardcoded default cuts new work from the wrong
    commit. A named base is local, so a stacked branch's unmerged parent needs no fetch; with
    none, origin/develop is fetched first. --no-track keeps the new branch from inheriting its
    base as upstream, which made it look pushed at birth (this project, 2026-09-26).
    """
    if not slug or not all(character.isalnum() or character == "-" for character in slug):
        raise SystemExit(f"slug must be lowercase kebab-case: {slug!r}")

    branch = f"feature/{slug}"
    path = sibling_path(slug)

    if path.exists():
        raise SystemExit(f"{path} already exists. Remove it first: mise run worktree:remove {slug}")

    if base is None:
        _git("fetch", "origin", "--prune", "--quiet")
    start = base or "origin/develop"
    _git("worktree", "add", "--no-track", "-b", branch, str(path), start)
    print(f"created {path} on {branch} from {start}\n")
    return _ready(path, slug)


def _ready(path: Path, slug: str) -> int:
    """Trust the new worktree's own mise.toml through the founding gate, then run its setup.

    SETUP IS NOT OPTIONAL. Without it the worktree has no .venv, an untrusted mise.toml and no
    hooks, so the gate cannot run and a commit is refused. THE NEW WORKTREE MANAGES ITS OWN
    ENVIRONMENT: the caller's VIRTUAL_ENV is removed, not inherited (D.12), for every command.
    TRUST IS NEVER INHERITED (A.27): the founding policy judges this worktree's mise.toml, and
    only then is that file trusted, by its own path.
    """
    print("running setup in the new worktree...")
    env = setup_environment(os.environ)

    def run(command: list[str], cwd: Path, stdin: str | None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command, cwd=cwd, input=stdin, env=env, capture_output=True, text=True, check=False
        )

    decision = machine_trust.trust(
        path,
        (path / "mise.toml").read_text(encoding="utf-8"),
        allows=lambda text: machine_trust.founding_allows(text, run=run),
        run=run,
        events=machine_trust.EVENTS,
    )
    if not decision.trusted:
        print(
            f"\n{path}'s mise.toml was not trusted: the founding policy refused it or mise "
            f"could not trust it. Remove the worktree:\n  mise run run worktree:remove {slug}",
            file=sys.stderr,
        )
        return 1
    if subprocess.run(["mise", "run", "setup"], cwd=path, check=False, env=env).returncode != 0:
        print(
            f"\nsetup failed in {path}. The worktree exists but is not usable. "
            f"Fix setup there, or remove it:\n  mise run run worktree:remove {slug}",
            file=sys.stderr,
        )
        return 1

    print(f"\nnext:\n  cd {path}")
    return 0


def cmd_list() -> int:
    for worktree in parse_worktrees():
        branch = worktree.get("branch", "").removeprefix("refs/heads/") or "(detached)"
        flags = [f for f in ("locked", "prunable") if f in worktree]
        suffix = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{worktree['worktree']}  {branch}{suffix}")
    return 0


def _settle_environment(path: Path, before: str) -> None:
    """THE ENVIRONMENT FOLLOWS THE LOCK, as sync's does after a pull (D.38, D.103).

    Called only once a rebase FINISHES: mid-rebase the lock may hold conflict markers. A lock
    that changed but would not install fails the refresh, since success would then describe an
    environment that no longer matches its lock. follow_lock is read from env_sync at call time,
    so sync and refresh share one function and one point of proof.
    """
    import env_sync

    synced = env_sync.follow_lock(path, before)
    if synced.lock_changed and not synced.installed:
        raise SystemExit(
            f"rebased {path}, but uv.lock changed and uv sync --locked exited "
            f"{synced.install_exit_code}: the environment no longer matches the lock"
        )


def cmd_refresh(slug: str) -> int:
    """Rebase the worktree's branch onto current origin/develop.

    Run from INSIDE the worktree, which is the documented pattern; objects are
    shared with the main clone so no network round-trip is needed. Rebase labels
    are worktree-local refs, so this cannot interfere with a rebase running in
    another worktree.

    REFUSES ON A DIRTY TREE rather than using --autostash. git's manual warns
    that the stash application after a successful rebase "might result in
    non-trivial conflicts", and rebase.autoStash defaults to false for that
    reason. Autostash hides work in a stash nobody created.
    """
    path = sibling_path(slug)
    if not path.exists():
        raise SystemExit(f"{path} does not exist")

    branch = f"feature/{slug}"
    if branch in {"feature/develop", "feature/main"} or slug in {"develop", "main"}:
        # Never rebase an integration branch. Unreachable via the slug form, and
        # stated so the constraint is a rule rather than an accident of naming.
        raise SystemExit(f"refusing: {branch} is an integration branch, not a feature branch")

    status = git_bytes("status", "--porcelain", "-z", cwd=path)
    if status.stdout.strip(b"\0"):
        raise SystemExit(
            f"refusing: {path} has uncommitted changes.\n"
            "Commit or discard them first -- rebasing over a dirty tree either "
            "refuses, or with --autostash hides the work in a stash you did not "
            "create and may not look for."
        )

    _git("fetch", "origin", "--prune", "--quiet")

    # REPORT AN OBSERVED STATE CHANGE, NOT PARSED OUTPUT.
    #
    # The first version printed `result.stdout` and fell back to "already
    # matches origin/develop" when it was empty. git rebase writes "Successfully
    # rebased and updated..." to STDERR, so a successful rebase leaves stdout
    # empty -- and the task confidently reported that a worktree three PRs behind
    # already matched develop.
    #
    # The rule this violates: never parse human-readable git output. It is
    # explicitly not a stable interface, and the convention it follows is
    # human-readable to stderr, data to stdout. Comparing SHAs before and after
    # is plumbing, and it cannot describe something that did not happen.
    before = git_run("rev-parse", "HEAD", cwd=path).stdout.strip()

    result = git_run("rebase", "origin/develop", cwd=path)
    if result.returncode != 0:
        print((result.stdout + result.stderr).strip(), file=sys.stderr)
        raise SystemExit(
            f"rebase stopped in {path}. Read the conflicts with "
            f"`mise run run worktree:conflicts {slug}`, resolve them, then "
            f"`mise run run worktree:continue {slug}`; or abandon with `git rebase --abort`."
        )

    after = git_run("rev-parse", "HEAD", cwd=path).stdout.strip()
    target = git_run("rev-parse", "origin/develop", cwd=path).stdout.strip()
    _settle_environment(path, before)

    if before == after:
        print(f"{path} was already on origin/develop ({target[:12]})")
    else:
        print(f"{path}: {before[:12]} -> {after[:12]} (onto {target[:12]})")
    return 0


def _delete_branch(branch: str) -> int:
    """branch -d, never -D: an unmerged branch is reported, never lost."""
    result = git_run("branch", "-d", branch, cwd=ROOT)
    if result.returncode != 0:
        print(
            f"worktree removed, but branch {branch} was NOT deleted:\n"
            f"  {result.stderr.strip()}\n"
            "That refusal means the branch is unmerged. Merge it, or delete it "
            "deliberately with `git branch -D`.",
            file=sys.stderr,
        )
        return 1

    print(f"deleted branch {branch}")
    return 0


def cmd_remove(slug: str) -> int:
    path = sibling_path(slug)
    branch = f"feature/{slug}"

    if not path.exists():
        # ALREADY GONE IS THE END STATE, NOT AN ERROR (D.105). prune removes only registrations
        # whose directories are missing; the branch, if any, goes exactly as below: branch -d.
        _git("worktree", "prune")
        found = git_run("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", cwd=ROOT)
        if found.returncode == 1:
            print(f"{path} already removed; branch {branch} already deleted")
            return 0
        if found.returncode != 0:
            raise SystemExit(
                f"could not tell whether {branch} exists: rev-parse exited {found.returncode}"
            )
        print(f"{path} already removed")
        return _delete_branch(branch)

    _git("worktree", "remove", str(path))
    print(f"removed {path}")
    return _delete_branch(branch)


def main() -> int:
    match sys.argv[1:]:
        case ["list"]:
            return cmd_list()
        case ["add", slug]:
            return cmd_add(slug)
        case ["add", slug, base]:
            return cmd_add(slug, base)
        case ["refresh", slug]:
            return cmd_refresh(slug)
        case ["remove", slug]:
            return cmd_remove(slug)
        case other:
            usage = "usage: worktree.py add <slug> [base] | list | refresh <slug> | remove <slug>"
            raise SystemExit(f"{usage}  (got {other})")


if __name__ == "__main__":
    raise SystemExit(main())
