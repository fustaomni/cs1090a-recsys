"""Plan-file conflicts are resolved as data during a rebase or a merge (D.129).

Two branches that each add a step append to the end of the same three files, so a merge
conflicts in all of them. The resolver reads the base, ours and theirs from the index, unions
what each side appended, refuses an id issued twice or an entry edited on both sides, and
validates the three files together before anything is staged.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from plan_edit import add, amend
from plan_init import write_day_one

IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
FILES = ("context/plan.toml", "context/plan-ids.toml", "context/plan-trace.toml")


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=check
    )


def _subject() -> ModuleType:
    assert importlib.util.find_spec("plan_conflicts") is not None, "no plan-conflict resolver"
    return importlib.import_module("plan_conflicts")


def _repo(tmp_path: Path) -> Path:
    """A day-one plan on develop, committed, with a branch theirs at the same commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "develop")
    write_day_one(repo)
    _git(repo, "add", "context")
    _git(repo, "commit", "--quiet", "-m", "day one")
    _git(repo, "branch", "theirs")
    return repo


def _add(repo: Path, tmp_path: Path, step: str, title: str, ref: str) -> None:
    spec = tmp_path / f"add-{ref}.toml"
    spec.write_text(
        "[[steps]]\n"
        f'id = "{step}"\n'
        f'title = "{title}"\n'
        'thread = "A"\n'
        'done_when = [ { kind = "proof", test = "tests/t.py::test_probe" } ]\n\n'
        "[trace]\n"
        'source = "TEMPLATE"\n'
        f'ref = "{ref}"\n'
        f'text = "{title}"\n',
        encoding="utf-8",
    )
    assert add([str(spec)], root=repo) == 0, spec.read_text(encoding="utf-8")


def _amend(repo: Path, tmp_path: Path, title: str, ref: str) -> None:
    spec = tmp_path / f"amend-{ref}.toml"
    spec.write_text(f'id = "A.1"\n\n[set]\ntitle = "{title}"\n', encoding="utf-8")
    assert amend([str(spec)], root=repo) == 0, spec.read_text(encoding="utf-8")


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "context")
    _git(repo, "commit", "--quiet", "-m", message)


def _diverge(repo: Path, tmp_path: Path, ours: tuple[str, str], theirs: tuple[str, str]) -> None:
    """develop adds ours, theirs adds theirs, and merging theirs into develop conflicts."""
    _add(repo, tmp_path, ours[0], ours[1], "ours")
    _commit(repo, "ours")
    _git(repo, "switch", "--quiet", "theirs")
    _add(repo, tmp_path, theirs[0], theirs[1], "theirs")
    _commit(repo, "theirs")
    _git(repo, "switch", "--quiet", "develop")
    merged = _git(repo, "merge", "--no-ff", "--no-commit", "theirs", check=False)
    assert merged.returncode != 0, "the two additions were expected to conflict"


def _unmerged(repo: Path) -> set[str]:
    listed = _git(repo, "diff", "--name-only", "--diff-filter=U").stdout
    return set(listed.split())


def test_entries_appended_on_both_sides_are_unioned(tmp_path: Path) -> None:
    """A.2 from ours and A.3 from theirs both survive, and nothing is left unmerged."""
    repo = _repo(tmp_path)
    _diverge(repo, tmp_path, ("A.2", "ours step"), ("A.3", "theirs step"))
    subject = _subject()
    subject.resolve(repo)
    plan = (repo / FILES[0]).read_text(encoding="utf-8")
    issued = (repo / FILES[1]).read_text(encoding="utf-8")
    trace = (repo / FILES[2]).read_text(encoding="utf-8")
    for step in ("A.1", "A.2", "A.3"):
        assert f'id = "{step}"' in plan, plan
        assert f'id = "{step}"' in issued, issued
    assert 'ref = "ours"' in trace and 'ref = "theirs"' in trace, trace
    assert _unmerged(repo) == set(), _unmerged(repo)


def test_one_id_issued_on_both_sides_is_refused(tmp_path: Path) -> None:
    """Both sides issued A.2 with different titles: refused by name, nothing resolved."""
    repo = _repo(tmp_path)
    _diverge(repo, tmp_path, ("A.2", "ours meaning"), ("A.2", "theirs meaning"))
    subject = _subject()
    with pytest.raises(subject.PlanConflictError) as refused:
        subject.resolve(repo)
    assert "A.2" in str(refused.value), refused.value
    assert _unmerged(repo) == set(FILES), _unmerged(repo)


def test_one_entry_edited_on_both_sides_is_refused(tmp_path: Path) -> None:
    """Both sides retitled A.1 differently: refused by name, nothing resolved."""
    repo = _repo(tmp_path)
    _amend(repo, tmp_path, "ours retitled", "ours")
    _commit(repo, "ours")
    _git(repo, "switch", "--quiet", "theirs")
    _amend(repo, tmp_path, "theirs retitled", "theirs")
    _commit(repo, "theirs")
    _git(repo, "switch", "--quiet", "develop")
    merged = _git(repo, "merge", "--no-ff", "--no-commit", "theirs", check=False)
    assert merged.returncode != 0, "the two edits were expected to conflict"
    subject = _subject()
    with pytest.raises(subject.PlanConflictError) as refused:
        subject.resolve(repo)
    assert "A.1" in str(refused.value), refused.value
    assert FILES[0] in _unmerged(repo), _unmerged(repo)


def test_the_resolution_is_validated_before_it_is_staged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the plan's own validation refuses the union, nothing is written or staged."""
    repo = _repo(tmp_path)
    _diverge(repo, tmp_path, ("A.2", "ours step"), ("A.3", "theirs step"))
    subject = _subject()

    def refuse(documents: object) -> object:
        raise ValueError("the plan's own validation refused the union")

    monkeypatch.setattr(subject, "_validated", refuse)
    with pytest.raises(subject.PlanConflictError):
        subject.resolve(repo)
    assert _unmerged(repo) == set(FILES), _unmerged(repo)


def _spine(subject: ModuleType) -> None:
    assert hasattr(subject, "run"), "plan:resolve has no entry point on the spine"


def _conflict_elsewhere(repo: Path) -> None:
    """develop and theirs each add other.txt differently; no plan file changes."""
    for branch, text in (("theirs", "theirs\n"), ("develop", "ours\n")):
        _git(repo, "switch", "--quiet", branch)
        (repo / "other.txt").write_text(text, encoding="utf-8")
        _git(repo, "add", "other.txt")
        _git(repo, "commit", "--quiet", "-m", branch)
    merged = _git(repo, "merge", "--no-ff", "--no-commit", "theirs", check=False)
    assert merged.returncode != 0, "other.txt was expected to conflict"


def test_no_operation_is_refused_by_its_coded_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no merge or rebase in progress, the policy refuses by its code."""
    repo = _repo(tmp_path)
    subject = _subject()
    _spine(subject)
    assert subject.run(repo) != 0
    assert "ERR_PLAN_RESOLVE_NO_OPERATION" in capsys.readouterr().out


def test_no_plan_file_in_conflict_is_refused_by_its_coded_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A merge stopped on another file only: the policy refuses by its code."""
    repo = _repo(tmp_path)
    _conflict_elsewhere(repo)
    subject = _subject()
    _spine(subject)
    assert subject.run(repo) != 0
    assert "ERR_PLAN_RESOLVE_NOTHING_CONFLICTED" in capsys.readouterr().out


def test_a_conflicted_merge_is_resolved_on_the_spine(tmp_path: Path) -> None:
    """The union fixture, run through the spine: resolved, and nothing left unmerged."""
    repo = _repo(tmp_path)
    _diverge(repo, tmp_path, ("A.2", "ours step"), ("A.3", "theirs step"))
    subject = _subject()
    _spine(subject)
    assert subject.run(repo) == 0
    assert _unmerged(repo) == set(), _unmerged(repo)


def test_an_absent_request_is_refused_by_the_policy(tmp_path: Path) -> None:
    """runs.plan_resolve refuses when no resolve plan is supplied, never reading it as clean."""
    subject = _subject()
    plan = subject.plan_resolve(_repo(tmp_path))
    found = subject.evaluate(plan, "not_plan_resolve", subject.POLICY, subject.ENTRYPOINT)
    codes = {rule.code for rule in found.rules if rule.outcome == "fail"}
    assert "ERR_PLAN_RESOLVE_INPUT_MISSING" in codes, found


def test_an_argument_is_refused_naming_no_task(capsys: pytest.CaptureFixture[str]) -> None:
    """An argument is refused, and the refusal names no task this repository does not declare."""
    subject = _subject()
    assert subject.main(["unexpected"]) != 0
    assert "mise run run" not in capsys.readouterr().out
