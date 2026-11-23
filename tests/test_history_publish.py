"""A verified mirror replaces origin's history only through history:publish (A.366).

history:rewrite records each ref's tip when it cuts the mirror. history:publish reads those
leases, compares them with what the remote holds now, and refuses the whole publish if any ref
has moved since. Without --yes it reports what it would push and pushes nothing. With it, the
ruleset's deletion and non-fast-forward rules are lifted, every branch and tag is pushed in one
atomic push leased on its recorded tip, and the ruleset is restored from its contract whether or
not the push succeeded. These run real git against a bare scratch origin; only the ruleset, which
lives on GitHub, is a recording stand-in, and a failed push is the origin's own pre-receive hook.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import BaseModel

import spine
from nonvacuous import nonempty

DROPPED = "Scratch-Drop: zqx"
KEEP = "Plan-Step: A.1"


def _subject() -> ModuleType:
    return importlib.import_module("history_publish")


def _git(repo: Path, *argv: str) -> str:
    done = subprocess.run(["git", *argv], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _commit(work: Path, name: str, message: str) -> None:
    (work / name).write_text(f"{name}\n", encoding="utf-8")
    _git(work, "add", name)
    _git(work, "commit", "-q", "-m", message)
    _git(work, "push", "-q", "origin", "develop")


def _origin(tmp_path: Path) -> tuple[Path, Path]:
    """A bare origin on develop, and a working clone that pushes to it; no signing, no hooks."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "develop", str(origin))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    for argv in (
        ["config", "user.name", "zqx"],
        ["config", "user.email", "zqx"],
        ["config", "commit.gpgsign", "false"],
        ["config", "core.hooksPath", str(work / ".no-hooks")],
        ["switch", "-q", "-c", "develop"],
    ):
        _git(work, *argv)
    _commit(work, "a.txt", f"chore(scratch): one\n\n{KEEP}\n{DROPPED}")
    _git(work, "tag", "-a", "v0", "-m", "v0")
    _git(work, "push", "-q", "origin", "v0")
    return origin, work


def _tips(origin: Path) -> dict[str, str]:
    listed = _git(origin, "for-each-ref", "--format=%(objectname) %(refname)")
    return {ref: sha for sha, ref in (line.split(" ", 1) for line in listed.splitlines())}


def _mirror(tmp_path: Path, origin: Path) -> Path:
    rewrite = importlib.import_module("history_rewrite")
    rules = rewrite.RewriteRules.model_validate(
        {"drop_lines": ["^Scratch-Drop:"], "replace_text": [], "cited_paths": []}
    )
    mirror = tmp_path / "mirror.git"
    rewrite.rewrite(str(origin), mirror, rules)
    return mirror


class _Ruleset:
    """The ruleset on GitHub, recorded: every lift and restore, in order."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def lift(self) -> bool:
        self.calls.append("lift")
        return True

    def restore(self) -> bool:
        self.calls.append("restore")
        return True


def test_without_yes_nothing_is_pushed_and_every_ref_is_reported(tmp_path: Path) -> None:
    subject = _subject()
    origin, _ = _origin(tmp_path)
    before = _tips(origin)
    mirror = _mirror(tmp_path, origin)
    ruleset = _Ruleset()
    report = subject.publish(mirror, subject.GitRemote(str(origin), mirror), ruleset, execute=False)
    assert _tips(origin) == before
    assert ruleset.calls == []
    assert report.pushed is False
    assert {update.ref for update in report.plan.refs} == set(before)


def test_every_ref_is_pushed_with_a_lease_on_the_tip_recorded_when_the_mirror_was_cut(
    tmp_path: Path,
) -> None:
    subject = _subject()
    origin, _ = _origin(tmp_path)
    before = _tips(origin)
    mirror = _mirror(tmp_path, origin)
    assert subject.load_leases(mirror).refs == before
    ruleset = _Ruleset()
    report = subject.publish(mirror, subject.GitRemote(str(origin), mirror), ruleset, execute=True)
    assert report.pushed is True
    assert ruleset.calls == ["lift", "restore"]
    assert _tips(origin) == _tips(mirror)
    assert _tips(origin) != before
    for update in nonempty(report.plan.refs):
        assert update.old == before[update.ref]


def test_a_ref_moved_since_the_mirror_was_cut_refuses_the_whole_publish(tmp_path: Path) -> None:
    subject = _subject()
    origin, work = _origin(tmp_path)
    mirror = _mirror(tmp_path, origin)
    _commit(work, "b.txt", f"chore(scratch): pushed after the cut\n\n{KEEP}")
    moved = _tips(origin)
    ruleset = _Ruleset()
    with pytest.raises(subject.PublishRefusedError):
        subject.publish(mirror, subject.GitRemote(str(origin), mirror), ruleset, execute=True)
    assert _tips(origin) == moved
    assert ruleset.calls == []


def test_the_ruleset_is_restored_from_its_contract_even_when_the_push_fails(
    tmp_path: Path,
) -> None:
    subject = _subject()
    origin, _ = _origin(tmp_path)
    before = _tips(origin)
    mirror = _mirror(tmp_path, origin)
    hook = origin / "hooks" / "pre-receive"
    _git(origin, "config", "core.hooksPath", str(hook.parent))
    hook.write_text("#!/bin/sh\necho refused by the scratch origin >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    ruleset = _Ruleset()
    report = subject.publish(mirror, subject.GitRemote(str(origin), mirror), ruleset, execute=True)
    assert report.pushed is False
    assert report.ruleset_restored is True
    assert ruleset.calls == ["lift", "restore"]
    assert _tips(origin) == before


def test_a_branch_origin_holds_that_the_mirror_lacks_refuses_the_whole_publish(
    tmp_path: Path,
) -> None:
    """A branch only origin holds would keep its old history reachable, so nothing is pushed."""
    subject = _subject()
    origin, work = _origin(tmp_path)
    mirror = _mirror(tmp_path, origin)
    _git(work, "push", "-q", "origin", "develop:refs/heads/feature/elsewhere")
    held = _tips(origin)
    ruleset = _Ruleset()
    with pytest.raises(subject.PublishRefusedError) as refused:
        subject.publish(mirror, subject.GitRemote(str(origin), mirror), ruleset, execute=True)
    assert "refs/heads/feature/elsewhere" in str(refused.value)
    assert _tips(origin) == held
    assert ruleset.calls == []


def _failed(evidence: BaseModel, subject_name: str, policy: Path, entrypoint: str) -> set[str]:
    found = spine.evaluate(evidence, subject_name, policy, entrypoint)
    return {rule.code for rule in found.rules if rule.outcome == "fail"}


def test_the_publish_plan_is_judged_by_its_policy() -> None:
    subject = _subject()
    judged = (subject.SUBJECT, subject.POLICY, subject.ENTRYPOINT)
    plan = subject.PublishPlan(mirror="m", remote="r", refs=[], moved=["refs/heads/develop"])
    refused = {"ERR_HISTORY_PUBLISH_NO_REFS", "ERR_HISTORY_PUBLISH_REF_MOVED"}
    assert _failed(plan, *judged) == refused
    update = subject.RefUpdate(ref="refs/heads/develop", old="a" * 40, new="b" * 40)
    clean = plan.model_copy(update={"refs": [update], "moved": []})
    assert _failed(clean, *judged) == set()
    assert "ERR_HISTORY_PUBLISH_PLAN_MISSING" in _failed(clean, "not_history_publish", *judged[1:])
