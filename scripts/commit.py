# scripts/commit.py
"""Committing, as a task that decides before it acts.

WHAT THIS FIXES. Every commit in this repository was made by hand as
`git commit --file /tmp/commit-msg.txt --no-verify`. Two defects in one habit:

    NOT A TASK      mise.toml states that every project operation is a task,
                    "not a remembered command, not a paste from scrollback".
                    The most frequent operation here was the exception.

    --no-verify     the pre-commit hooks -- start:check, fmt, lint -- were
                    skipped on EVERY commit. The gate was only reached at push
                    time, so a protected-branch commit or an unformatted file
                    was caught late or not at all.

THIS MODULE PLANS; IT DOES NOT YET ACT.

plan_commit answers one question -- may this commit proceed, and with what --
and returns the answer as a command-outcome/v1 envelope. Running git is a
separate concern with its own tests, written next. Splitting them keeps the
decision pure and testable without a repository, and means a caller can show
what WOULD happen before anything is staged.

NAMED PATHS, NEVER -A. `git add -A` swept a stray zero-byte file into a commit
earlier in this project; scripts/check_repo_hygiene.py exists because of it.
Naming the paths makes the content of a commit a decision rather than whatever
the working tree happened to hold.

THE ORDER OF REFUSALS IS DELIBERATE. The branch is checked first because it is
the cheapest and most fundamental guard. The subject is checked BEFORE the
paths, so a rejected message never leaves a half-staged index behind.

ONLY THE NAMED PATHS ARE COMMITTED (D.343). A path someone else staged -- an IDE, a stray
`git add` -- is refused by name once the plan allows the commit, and commit:unstage is the way
out: it unstages named, staged paths with `git restore --staged`, never reset, so no file on
disk changes. The commit names its paths as a pathspec too, a second protection, except while a
merge is held (D.360): git refuses a pathspec then, and the index, already exactly the named
paths, is committed whole as the merge commit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath

from command_outcome import CommandOutcome
from gitenv import git as scrubbed_git

__all__ = [
    "CONVENTIONAL_SUBJECT",
    "PROTECTED",
    "execute_commit",
    "execute_unstage",
    "main",
    "plan_commit",
    "run_git",
]

ROOT = Path(__file__).resolve().parent.parent

# GITFLOW: work happens on a feature branch cut from origin/develop. The same
# set start:check guards, restated here because --no-verify meant that guard
# never ran on a commit.
PROTECTED = frozenset({"develop", "main"})

# CONVENTIONAL COMMITS, ANCHORED AT BOTH ENDS.
#
# An unanchored pattern accepts prose that merely CONTAINS a type -- "this is
# not a feat(x): subject" would match in the middle and pass. The ^ and the
# explicit alternation are what make this a format check rather than a search.
#
# The scope is optional because "fix: ..." is valid; the ! is optional because a
# breaking change marks itself.
CONVENTIONAL_SUBJECT = re.compile(
    r"^(?:feat|fix|refactor|test|docs|chore|ci|build|perf|style|revert)"
    r"(?:\([a-z0-9][a-z0-9:_-]*\))?!?: .+$"
)


def _outcome(
    code: str, message: str, verdict: str, command: str = "commit", **data: object
) -> CommandOutcome:
    """One envelope, so every exit from this module has the same shape."""
    return CommandOutcome.model_validate(
        {
            "command": command,
            "outcome": verdict,
            "code": code,
            "message": message,
            "data": data,
        }
    )


def plan_commit(
    branch: str,
    message: str,
    paths: Sequence[str],
    root: Path = ROOT,
    tracked: frozenset[str] = frozenset(),
    amend: bool = False,
    published: bool | None = False,
    root_commit: bool = False,
) -> CommandOutcome:
    """Decide whether this commit may proceed, and say why when it may not.

    REFUSED, NOT FAILED. Every negative answer here is the command working
    correctly and declining: the branch is protected, the subject is not
    conventional, no path was named. None of them is a crash, and the exit code
    says so -- 2 rather than 1 -- so a caller can tell a rule from a bug.
    """
    # THE ROOT COMMIT IS THE ONE EXCEPTION (A.5): no branch can be cut from a main with
    # no commit, so the commit that creates it is allowed here, as start:check allows it.
    if branch in PROTECTED and not root_commit:
        return _outcome(
            "protected_branch",
            f"refusing to commit on {branch!r}: work happens on a feature branch "
            "cut from origin/develop",
            "refused",
            branch=branch,
        )

    # AMENDING REWRITES A COMMIT, so only one nobody else has (D.101): published, or unknown
    # because git could not say, is refused before anything is staged.
    if amend and published is not False:
        code = "already_published" if published else "publication_unknown"
        reason = (
            f"refusing to amend HEAD on {branch!r}: it is already on origin"
            if published
            else f"refusing to amend HEAD on {branch!r}: git cannot say whether it is published"
        )
        return _outcome(code, reason, "refused", branch=branch)

    # THE FIRST LINE IS THE SUBJECT. A body may say anything; the subject is the
    # part every tool, changelog and reader depends on.
    subject = message.split("\n", 1)[0]
    if CONVENTIONAL_SUBJECT.match(subject) is None:
        return _outcome(
            "unconventional_subject",
            f"the subject {subject!r} is not a conventional commit: "
            "expected type(scope): description",
            "refused",
            subject=subject,
        )

    if not paths:
        return _outcome(
            "no_paths_named",
            "no paths named: committing nothing and reporting success is not an outcome",
            "refused",
        )

    # A MISTYPED PATH WOULD OTHERWISE STAGE NOTHING AND COMMIT NOTHING, while
    # the command reported success -- the claim-without-effect shape this
    # repository keeps removing.
    # A TRACKED PATH ABSENT FROM DISK IS A DELETION, not a typo: `git add` records its
    # removal (since git 2.0), so only a path neither on disk nor tracked is refused (D.79).
    missing = [name for name in paths if not (root / name).exists() and name not in tracked]
    if missing:
        return _outcome(
            "path_not_found",
            f"named but not on disk: {', '.join(sorted(missing))}",
            "refused",
            missing=sorted(missing),
        )

    return _outcome(
        "ready_to_commit",
        f"{len(paths)} path(s) ready on {branch}",
        "success",
        branch=branch,
        subject=subject,
        # A LIST, NOT A TUPLE: JsonValue admits lists, and a tuple would fail at
        # the contract boundary rather than silently serialising.
        paths=list(paths),
    )


GitRunner = Callable[[list[str]], tuple[int, str]]
NEWLINE = chr(10)


def run_git(argv: list[str]) -> tuple[int, str]:
    """The real boundary: run git; report its code, and stdout on success or stderr on failure.

    STDOUT ON SUCCESS (D.102): an amend reads HEAD before and after, which git prints on stdout.
    Every other caller reads the text only on failure, where it is still stderr.
    """
    done = scrubbed_git(*argv, cwd=ROOT)
    if done.returncode == 0:
        return 0, done.stdout.strip()
    # BOTH STREAMS ON FAILURE (A.12): git prints some refusals, "nothing to commit" among
    # them, on stdout, and a reason read from stderr alone was lost.
    reason = [part.strip() for part in (done.stderr, done.stdout) if part.strip()]
    return done.returncode, NEWLINE.join(reason)


def publication(branch: str, git: GitRunner = run_git) -> bool | None:
    """Whether HEAD is on origin/<branch>: True, False, or None when git cannot say (D.101).

    The same observation pr's lease makes (D.87). rev-parse --verify --quiet exits 1 for an
    absent ref: never pushed, so local. merge-base --is-ancestor exits 0 when HEAD is contained,
    1 when it is not; any other status is an error, and an error is never read as local.
    """
    ref = f"refs/remotes/origin/{branch}"
    code, _ = git(["rev-parse", "--verify", "--quiet", ref])
    if code == 1:
        return False
    if code != 0:
        return None
    code, _ = git(["merge-base", "--is-ancestor", "HEAD", ref])
    return {0: True, 1: False}.get(code)


UNSTAGE = "commit:unstage"


def _staged(git: GitRunner) -> tuple[frozenset[str], str | None]:
    """The staged paths, NUL-separated so any name survives; git's error when it cannot say."""
    code, listed = git(["diff", "--cached", "--name-only", "-z"])
    if code != 0:
        return frozenset(), listed
    return frozenset(name for name in listed.split("\0") if name), None


def _covered(entry: str, paths: Sequence[str]) -> bool:
    """Is entry a named path, or inside a named directory? By parts: a/bc is not under a/b."""
    target = PurePosixPath(entry).parts
    for name in paths:
        named = PurePosixPath(name).parts
        if target[: len(named)] == named:
            return True
    return False


def refuse_unnamed(
    paths: Sequence[str], staged: frozenset[str], held: bool = False
) -> CommandOutcome | None:
    """A staged path the commit was not given, refused by name with its remedy (D.343, D.371).

    A HELD MERGE IS COMMITTED WHOLE (D.360), so a path its merge staged is part of the merge:
    unstaging it would drop the merged side's change from the merge commit. The refusal stays,
    so a commit's contents are still a decision, but its remedy is to name the path too, and
    held and remedy are data, so a caller branches on them rather than on the message (D.371).
    """
    unnamed = sorted(entry for entry in staged if not _covered(entry, paths))
    if not unnamed:
        return None
    listed = ", ".join(unnamed)
    if held:
        message = (
            f"staged but not named, in a held merge: {listed}; name them too, since a merge "
            "is committed whole and unstaging them would drop them from it"
        )
        remedy = "name"
    else:
        message = f"staged but not named: {listed}; unstage them with commit:unstage"
        remedy = "unstage"
    return _outcome("staged_unnamed", message, "refused", unnamed=unnamed, held=held, remedy=remedy)


def _merge_held(git: GitRunner) -> bool:
    """Whether a merge is held: git names MERGE_HEAD's commit only while one is (D.360)."""
    code, named = git(["rev-parse", "-q", "--verify", "MERGE_HEAD"])
    return code == 0 and bool(named)


def execute_unstage(paths: Sequence[str], git: GitRunner = run_git) -> CommandOutcome:
    """commit:unstage -- named, staged paths leave the index, their files untouched (D.343).

    `git restore --staged`, NEVER reset: reset's other modes discard work, and restore --staged
    has no such neighbour. A named path that is not staged is refused by name: reporting it as
    unstaged would be a claim without effect.
    """
    if not paths:
        message = "no paths named: name the paths to unstage"
        return _outcome("no_paths_named", message, "refused", command=UNSTAGE)
    staged, unreadable = _staged(git)
    if unreadable is not None:
        message = "could not read the index: " + unreadable
        return _outcome("index_unreadable", message, "failed", command=UNSTAGE)
    idle = sorted(name for name in paths if not any(_covered(entry, [name]) for entry in staged))
    if idle:
        message = f"named but not staged: {', '.join(idle)}"
        return _outcome("not_staged", message, "refused", command=UNSTAGE, idle=idle)
    code, err = git(["restore", "--staged", "--", *paths])
    if code != 0:
        return _outcome("unstage_failed", "git refused: " + err, "failed", command=UNSTAGE)
    message = f"unstaged {len(paths)} path(s); their files are untouched"
    return _outcome("unstaged", message, "success", command=UNSTAGE, paths=list(paths))


def execute_commit(
    branch: str,
    message: str,
    paths: Sequence[str],
    git: GitRunner = run_git,
    root: Path = ROOT,
    amend: bool = False,
    root_commit: bool = False,
) -> CommandOutcome:
    """Stage the named paths and commit them, THROUGH THE HOOKS.

    NO --no-verify, which is why this task exists: every commit here carried it,
    so start:check, fmt and lint never ran on a commit.

    THE PLAN IS CONSULTED FIRST and its refusal returned untouched, so git is
    never reached when a rule says no.

    THE MESSAGE GOES THROUGH A FILE: -m is where shell quoting breaks.
    """
    # OBSERVED, NOT ASSUMED: git's own index says which absent paths are tracked deletions.
    absent = [name for name in paths if not (root / name).exists()]
    tracked = frozenset(
        name for name in absent if git(["ls-files", "--error-unmatch", "--", name])[0] == 0
    )
    published = publication(branch, git) if amend else False
    planned = plan_commit(
        branch=branch,
        message=message,
        paths=paths,
        root=root,
        tracked=tracked,
        amend=amend,
        published=published,
        root_commit=root_commit,
    )
    if planned.outcome != "success":
        return planned

    # THE INDEX IS READ ONLY ONCE THE RULES ALLOW A COMMIT (D.343): a refused plan never
    # reaches git, and a path someone else staged is refused before anything is staged.
    staged, unreadable = _staged(git)
    if unreadable is not None:
        return _outcome("index_unreadable", "could not read the index: " + unreadable, "failed")
    # A HELD MERGE IS KNOWN BEFORE THE REFUSAL (D.371): its remedy depends on it, and the
    # same observation decides below whether the index is committed whole.
    held = _merge_held(git)
    refused = refuse_unnamed(paths, staged, held)
    if refused is not None:
        return refused

    replaced = git(["rev-parse", "HEAD"])[1] if amend else ""
    code, err = git(["add", "--", *paths])
    if code != 0:
        return _outcome("stage_failed", "could not stage: " + err, "failed", paths=list(paths))

    # NOTHING STAGED IS A REFUSAL, decided before git is asked to commit (A.12): paths that
    # match HEAD stage nothing. --quiet exits 1 when the named paths have staged changes and
    # 0 when they have none; any other status is an error, never read as either. An amend
    # may change only the message, so it is exempt.
    if not amend:
        quiet, err = git(["diff", "--cached", "--quiet", "--", *paths])
        if quiet == 0:
            reason = "nothing to commit: the named paths match HEAD"
            return _outcome("nothing_staged", reason, "refused", paths=list(paths))
        if quiet != 1:
            reason = "could not read the stage: " + err
            return _outcome("stage_unverified", reason, "failed", paths=list(paths))

    # A HELD MERGE IS COMMITTED WHOLE (D.360). git refuses a pathspec while MERGE_HEAD exists
    # ("cannot do a partial commit during a merge"), and by now the index holds exactly the
    # named paths, any other refused above, so the merge's own index is the commit.
    scope = [] if held else ["--", *paths]
    # AN AMEND (D.101) KEEPS THE SAME SCOPE: only the named paths, or the held merge whole.
    if amend:
        scope = ["--amend", *scope]

    # delete_on_close=False IS THE DOCUMENTED ANSWER TO EXACTLY THIS NEED.
    #
    # git must reopen the file by name, so it cannot be deleted at close; it
    # must still be deleted afterwards, because a message file left behind is a
    # draft someone later mistakes for the current one.
    #
    # Two earlier shapes were worse. delete=False with os.unlink in a finally
    # met the second obligation and not the first: ruff's SIM115 saw that the
    # HANDLE escaped the context manager, so a raising write would leak it.
    #
    # CPython names this case: "to use the file name within a with statement,
    # set the delete_on_close parameter to be false. The latter approach is
    # recommended as it provides assistance in automatic cleaning of the
    # temporary file upon the context manager exit." The removal becomes the
    # context manager's obligation rather than mine, so no exit path skips it.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete_on_close=False, encoding="utf-8"
    ) as draft:
        draft.write(message if message.endswith(NEWLINE) else message + NEWLINE)
        # CLOSED SO GIT SEES THE WHOLE MESSAGE: an unflushed buffer would hand
        # git a truncated file, and a short commit message is worse than none.
        draft.close()
        code, err = git(["commit", "--file", draft.name, *scope])

    if code != 0:
        return _outcome("commit_failed", "git refused: " + err, "failed", branch=branch)

    subject = message.split(NEWLINE, 1)[0]
    if amend:
        # A REWRITE IS RECORDED AS ONE (D.102): the commit replaced, and its replacement.
        commit = git(["rev-parse", "HEAD"])[1]
        summary = f"amended {replaced[:12]} -> {commit[:12]} on {branch}: {len(paths)} path(s)"
        return _outcome(
            "amended",
            summary,
            "success",
            branch=branch,
            subject=subject,
            paths=list(paths),
            replaced=replaced,
            commit=commit,
        )
    return _outcome(
        "committed",
        "committed " + str(len(paths)) + " path(s) on " + branch,
        "success",
        branch=branch,
        subject=subject,
        paths=list(paths),
    )


def current_branch(git: GitRunner = run_git) -> str:
    """The branch this shell is on, read once at the boundary.

    PASSED IN, NOT READ INSIDE main(). The branch is ambient state; reading it
    where the decision happens would make the decision untestable without
    checking out a protected branch to prove the guard fires.

    SYMBOLIC-REF NAMES THE BRANCH EVEN BEFORE ITS FIRST COMMIT (A.5); rev-parse fails there,
    and the root commit was reported "on (unknown)". rev-parse remains for a detached HEAD.
    """
    code, name = git(["symbolic-ref", "--quiet", "--short", "HEAD"])
    if code == 0 and name:
        return name
    code, name = git(["rev-parse", "--abbrev-ref", "HEAD"])
    return name if code == 0 and name else "(unknown)"


def head_is_unborn(git: GitRunner = run_git) -> bool:
    """Whether HEAD names no commit yet: true only before the root commit (A.5).

    READ AT THE BOUNDARY, LIKE THE BRANCH, so a refusal inside the plan never reaches git.
    --verify --quiet exits 1 only for an absent commit; any other status is an error, and an
    error is never read as the root commit.
    """
    return git(["rev-parse", "--quiet", "--verify", "HEAD^{commit}"])[0] == 1


def main(
    argv: Sequence[str] | None = None,
    branch: str | None = None,
    git: GitRunner = run_git,
) -> int:
    """Commit the named paths, and report the outcome as data.

    STDOUT CARRIES THE ENVELOPE AND NOTHING ELSE, which is what
    command-outcome/v1 says it is for. A caller pipes this into jq; progress and
    diagnostics belong on stderr.

    THE EXIT CODE IS THE ENVELOPE'S -- 0, 1 or 2 -- so a shell branches on a
    refusal without parsing a word.

    --path REPEATS rather than splitting a list, so a path containing a space
    needs no quoting convention invented for it.
    """
    given = list(sys.argv[1:] if argv is None else argv)
    if given[:1] == ["unstage"]:
        unstage = argparse.ArgumentParser(prog=UNSTAGE, add_help=True)
        unstage.add_argument("--path", "-p", action="append", default=[])
        named = unstage.parse_args(given[1:])
        unstaged = execute_unstage(tuple(named.path), git=git)
        print(json.dumps(unstaged.model_dump(), indent=2))
        return unstaged.exit_code
    parser = argparse.ArgumentParser(prog="commit", add_help=True)
    parser.add_argument("--message", "-m", required=True)
    parser.add_argument("--path", "-p", action="append", default=[])
    parser.add_argument("--amend", action="store_true")
    parsed = parser.parse_args(given)

    on = branch if branch is not None else current_branch(git)
    outcome = execute_commit(
        branch=on,
        # ONLY A PROTECTED BRANCH ASKS: the exemption exists for nothing else.
        root_commit=on in PROTECTED and head_is_unborn(git),
        message=parsed.message,
        paths=tuple(parsed.path),
        git=git,
        amend=parsed.amend,
    )
    print(json.dumps(outcome.model_dump(), indent=2))
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
