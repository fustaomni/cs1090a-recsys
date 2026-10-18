# tests/conftest.py
"""Session-wide isolation from the git environment a hook exports (C.20).

pytest_configure runs once, before any test is collected: git_isolation removes
every repository-local variable machine.testing names, then requires the policy
to allow what remains -- so no test, existing or future, can reach the
repository a hook's GIT_DIR names.

ADAPTED FROM cscie103 (contracts/vendor-patches/tests/conftest.py.patch):
- eleven tests judge the real plan files or the published origin/develop, which exist
  only after plan:init (founding F6) and the first push (F7). Each is a strict expected
  failure only while its precondition is absent, and only with the exception that
  absence raises, so an unrelated breakage still fails. The sandbox test's AssertionError
  is the broad case: it holds only until F6.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NoReturn

import pytest

from git_isolation import isolate
from gitenv import git
from levels import classify, declared

ROOT = Path(__file__).resolve().parent.parent
NOFILE = FileNotFoundError
_FILES = "tests/test_plan_files.py::"
_TRAILERS = "tests/test_plan_trailers.py::"
_STATUS = "tests/test_plan_status.py::"
_MATRIX = "tests/test_plan_matrix.py::"

NEEDS_PLAN: dict[str, type[BaseException]] = {
    _FILES + "test_the_three_files_exist_and_validate": NOFILE,
    _FILES + "test_every_item_is_traced_in_both_directions": NOFILE,
    _FILES + "test_every_id_in_use_was_issued_and_none_was_retired": NOFILE,
    _FILES + "test_the_history_is_quoted_not_authored": NOFILE,
    _FILES + "test_the_task_reports_agreement_as_data": NOFILE,
    _TRAILERS + "test_a_step_named_mid_body_is_not_a_trailer": NOFILE,
    "tests/acceptance/test_sandbox.py::"
    "test_a_declared_task_runs_end_to_end_into_the_sandbox_ledger": AssertionError,
}
NEEDS_DEVELOP: dict[str, type[BaseException]] = {
    _STATUS + "test_this_repositorys_plan_is_decided_on_develop": SystemExit,
    _STATUS + "test_status_is_read_from_the_ref_never_the_disk": SystemExit,
    _MATRIX + "test_every_change_and_every_done_step_trace_to_each_other": SystemExit,
    _TRAILERS + "test_every_commit_names_a_plan_step": SystemExit,
}
PLAN_REASON = "context/plan.toml does not exist until plan:init (founding F6)"
DEVELOP_REASON = "origin/develop does not exist until the first push (founding F7)"


def pytest_configure() -> None:
    isolate(os.environ)


@pytest.fixture(autouse=True)
def _no_real_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reaches a real remote through pr's publication (D.39, D.174).

    A guard in the test process cannot stop a child process, so the publication is refused at
    its own seam. When D.39 moved push() onto a seam, four tests still patching subprocess.run
    ran a real git push against GitHub. A test that means to observe the publication patches
    pr._publish in its own body, which runs after this fixture and replaces the refusal.
    """
    import pr

    def refuse(*args: object, **_: object) -> NoReturn:
        raise RuntimeError(f"a test reached the real publication {args!r}; patch pr._publish")

    monkeypatch.setattr(pr, "_publish", refuse)


@pytest.fixture(autouse=True)
def _no_real_decision_record(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test appends a publication decision to the real run ledger (D.178).

    A test that means to observe the record passes its own recorder to publish().
    """
    import publish_push

    def discard(_: object) -> None:
        return None

    monkeypatch.setattr(publish_push, "_record", discard)


def _classify(items: list[pytest.Item]) -> None:
    """Every test takes its level from its directory, or the session is refused (A.39)."""
    levels = declared()
    refused: list[str] = []
    for item in items:
        names = [mark.name for mark in item.iter_markers()]
        try:
            item.add_marker(classify(item.nodeid, names, levels))
        except ValueError as problem:
            refused.append(str(problem))
    if refused:
        raise pytest.UsageError("tests without a level (A.39):\n" + "\n".join(refused))


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    _classify(items)
    plan_missing = not (ROOT / "context" / "plan.toml").is_file()
    probe = git("rev-parse", "--verify", "--quiet", "origin/develop", cwd=ROOT)
    develop_missing = probe.returncode != 0
    for item in items:
        if plan_missing and item.nodeid in NEEDS_PLAN:
            raised = NEEDS_PLAN[item.nodeid]
            item.add_marker(pytest.mark.xfail(reason=PLAN_REASON, raises=raised, strict=True))
        elif develop_missing and item.nodeid in NEEDS_DEVELOP:
            raised = NEEDS_DEVELOP[item.nodeid]
            item.add_marker(pytest.mark.xfail(reason=DEVELOP_REASON, raises=raised, strict=True))
