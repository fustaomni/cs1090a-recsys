# tests/test_worktree_lineage.py
"""A worktree is brought current by merge, and its lineage is never rewritten (A.191).

A rebase replaces every commit of a branch with a new one, so a branch already pushed would have
to be forced. History here is only ever added to: refresh merges origin/develop into the branch
with a merge commit naming its plan step, a stopped merge is concluded by committing it, and a
stopped rebase or merge is aborted back to the branch's own tip.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

import env_sync
import rebase_state
import spine
import worktree
from env_sync import EnvironmentSync

UNCHANGED = EnvironmentSync(lock_changed=False, installed=False, install_exit_code=None)


@pytest.fixture(autouse=True)
def _bare_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """No global git config, as on a bare CI runner: the proofs must not depend on the user's."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))


def _git(repo: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _diverged(tmp_path: Path) -> tuple[Path, str]:
    """main and feature change the same line; returns the repository and feature's own tip."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "merge.conflictStyle", "merge")
    _git(tmp_path, "config", "user.useConfigOnly", "true")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    (tmp_path / "f.txt").write_text("line1\nshared\nline3\n", encoding="utf-8")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "switch", "-q", "-c", "feature")
    (tmp_path / "f.txt").write_text("line1\nfeature\nline3\n", encoding="utf-8")
    _git(tmp_path, "commit", "-q", "-am", "feature change")
    _git(tmp_path, "switch", "-q", "main")
    (tmp_path / "f.txt").write_text("line1\nmain\nline3\n", encoding="utf-8")
    _git(tmp_path, "commit", "-q", "-am", "main change")
    _git(tmp_path, "switch", "-q", "feature")
    return tmp_path, _git(tmp_path, "rev-parse", "HEAD")


def _merging(tmp_path: Path) -> tuple[Path, str]:
    """feature merges main and stops on the conflict, its tip unchanged."""
    repo, tip = _diverged(tmp_path)
    _git(repo, "merge", "--no-ff", "-m", "merge main\n\nPlan-Step: A.1", "main", check=False)
    return repo, tip


def _require(name: str) -> None:
    assert hasattr(rebase_state, name), f"no {name}: the operation cannot be done by task"


def _refresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, step: str) -> list[tuple[str, ...]]:
    """Run refresh with every boundary faked; return the git commands it ran."""
    seen: list[tuple[str, ...]] = []
    heads = iter(["a" * 40, "b" * 40])

    def git_run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        seen.append(args)
        if args == ("rev-parse", "HEAD"):
            return subprocess.CompletedProcess([], 0, next(heads), "")
        return subprocess.CompletedProcess([], 0, "c" * 40, "")

    def clean(*_: object, **__: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, b"", b"")

    monkeypatch.setattr(worktree, "sibling_path", lambda slug: tmp_path)
    monkeypatch.setattr(worktree, "git_run", git_run)
    monkeypatch.setattr(worktree, "_git", lambda *args, **kwargs: "")
    monkeypatch.setattr(subprocess, "run", clean)
    monkeypatch.setattr(env_sync, "follow_lock", lambda path, before: UNCHANGED)
    parameters = inspect.signature(worktree.cmd_refresh).parameters
    assert "step" in parameters, "refresh takes no plan step, so its merge could name none"
    worktree.cmd_refresh("probe", step)
    return seen


def test_a_refresh_merges_develop_and_never_rebases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen = _refresh(monkeypatch, tmp_path, "A.95")
    merges = [args for args in seen if args[0] == "merge"]
    assert merges, seen
    assert merges[0][:2] == ("merge", "--no-ff"), merges
    assert merges[0][-1] == "origin/develop", merges
    assert not [args for args in seen if args[0] == "rebase"], seen


def test_the_merge_commit_names_its_plan_step(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen = _refresh(monkeypatch, tmp_path, "A.95")
    merge = next(args for args in seen if args[0] == "merge")
    assert "--no-commit" in merge, merge
    commit = next(args for args in seen if args[0] == "commit")
    message = commit[commit.index("-m") + 1]
    assert message.endswith("Plan-Step: A.95"), message


def test_a_refresh_without_a_plan_step_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(SystemExit) as refused:
        _refresh(monkeypatch, tmp_path, "not-a-step")
    assert "plan step" in str(refused.value.code), refused.value.code


def test_a_concluded_merge_keeps_every_commit_of_the_branch(tmp_path: Path) -> None:
    _require("conclude_merge")
    repo, tip = _merging(tmp_path)
    (repo / "f.txt").write_text("line1\nboth\nline3\n", encoding="utf-8")
    result = rebase_state.conclude_merge(repo)
    assert (result.outcome, rebase_state.conflicts(repo).operation) == ("finished", "none"), result
    parents = _git(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()
    assert parents[1:] == [tip, _git(repo, "rev-parse", "main")], parents
    assert _git(repo, "log", "-1", "--format=%s") == "merge main"


def test_a_merge_with_a_marker_left_is_not_concluded(tmp_path: Path) -> None:
    _require("conclude_merge")
    repo, _ = _merging(tmp_path)
    assert rebase_state.conclude_merge(repo).outcome == "refused"
    assert rebase_state.conflicts(repo).operation == "merge"


def test_conclude_without_a_merge_is_refused(tmp_path: Path) -> None:
    _require("conclude_merge")
    _git(tmp_path, "init", "-q", "-b", "main")
    assert rebase_state.conclude_merge(tmp_path).outcome == "refused"


def test_a_stopped_merge_is_aborted_back_to_its_tip(tmp_path: Path) -> None:
    _require("abort_operation")
    repo, tip = _merging(tmp_path)
    result = rebase_state.abort_operation(repo)
    assert result.outcome == "aborted", result
    head = _git(repo, "rev-parse", "HEAD")
    assert (head, rebase_state.conflicts(repo).operation) == (tip, "none"), result


def test_a_stopped_rebase_is_aborted_back_to_its_tip(tmp_path: Path) -> None:
    _require("abort_operation")
    repo, tip = _diverged(tmp_path)
    _git(repo, "rebase", "main", check=False)
    result = rebase_state.abort_operation(repo)
    assert result.outcome == "aborted", result
    head = _git(repo, "rev-parse", "HEAD")
    assert (head, rebase_state.conflicts(repo).operation) == (tip, "none"), result


def test_an_abort_with_nothing_in_progress_is_refused(tmp_path: Path) -> None:
    _require("abort_operation")
    _git(tmp_path, "init", "-q", "-b", "main")
    assert rebase_state.abort_operation(tmp_path).outcome == "refused"


def test_an_absent_abort_plan_is_refused_by_the_policy() -> None:
    _require("ABORT_POLICY")
    plan = rebase_state.AbortPlan(operation="merge")
    found = spine.evaluate(
        plan,
        "not_worktree_abort",
        rebase_state.ABORT_POLICY,
        rebase_state.ABORT_ENTRYPOINT,
    )
    codes = [rule.code for rule in found.rules if rule.outcome == "fail"]
    assert "ERR_ABORT_INPUT_MISSING" in codes, found


def test_an_absent_conclude_plan_is_refused_by_the_policy() -> None:
    _require("CONCLUDE_POLICY")
    plan = rebase_state.ContinuePlan(operation="merge", unmerged=(), with_markers=())
    found = spine.evaluate(
        plan,
        "not_worktree_conclude",
        rebase_state.CONCLUDE_POLICY,
        rebase_state.CONCLUDE_ENTRYPOINT,
    )
    codes = [rule.code for rule in found.rules if rule.outcome == "fail"]
    assert "ERR_CONCLUDE_INPUT_MISSING" in codes, found
