# tests/test_ci_rerun.py
"""ci:rerun retries only a run GitHub never started a job for, once, and reads it back (A.265)."""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

import ci_rerun

ROOT = Path(__file__).resolve().parent.parent
HEAD = "4be2b323fe8535938b2dc64af10e9d79f5550376"
OTHER = "0" * 40


def _run(head: str, status: str, conclusion: str | None, attempt: int, steps: int) -> str:
    """gh run view --json for one run, its single job given that many executed steps."""
    ran = [{"name": f"step {n}", "conclusion": "success"} for n in range(steps)]
    jobs = [{"databaseId": 1, "name": "quality gate", "conclusion": conclusion, "steps": ran}]
    run = {"databaseId": 42, "headSha": head, "status": status, "conclusion": conclusion}
    return json.dumps({**run, "attempt": attempt, "jobs": jobs if steps else []})


def _fake(monkeypatch: pytest.MonkeyPatch, *views: str) -> list[tuple[str, ...]]:
    """Fake gh and git: each run view answers with the next view; every call is recorded."""
    calls: list[tuple[str, ...]] = []
    answers = iter(views)

    def gh(*args: str) -> str:
        calls.append(args)
        return next(answers) if args[:2] == ("run", "view") else ""

    def git(*args: str, **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(args), 0, HEAD + "\n", "")

    monkeypatch.setattr(ci_rerun, "_gh", gh)
    monkeypatch.setattr(ci_rerun, "git", git)
    return calls


def _outcome(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(capsys.readouterr().out)
    return loaded


def _retried(calls: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    return [call for call in calls if call[:2] == ("run", "rerun")]


def test_a_run_for_another_head_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _fake(monkeypatch, _run(OTHER, "completed", "failure", 1, 0))
    assert ci_rerun.main(["42"]) == 2
    assert _outcome(capsys)["code"] == "rerun_refused"
    assert _retried(calls) == [], calls


def test_a_run_still_in_progress_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _fake(monkeypatch, _run(HEAD, "in_progress", None, 1, 0))
    assert ci_rerun.main(["42"]) == 2
    assert _outcome(capsys)["code"] == "rerun_refused"
    assert _retried(calls) == [], calls


def test_a_run_whose_jobs_ran_steps_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A job that ran steps failed on the code, which a retry must never paper over."""
    calls = _fake(monkeypatch, _run(HEAD, "completed", "failure", 1, 2))
    assert ci_rerun.main(["42"]) == 2
    assert _outcome(capsys)["code"] == "rerun_refused"
    assert _retried(calls) == [], calls


def test_a_failed_run_that_never_ran_a_step_is_retried_once_and_read_back(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _run(HEAD, "completed", "failure", 1, 0)
    after = _run(HEAD, "queued", None, 2, 0)
    calls = _fake(monkeypatch, before, after)
    assert ci_rerun.main(["42"]) == 0
    outcome = _outcome(capsys)
    assert outcome["code"] == "rerun_requested", outcome
    assert outcome["data"]["attempt"] == 2, outcome
    assert _retried(calls) == [("run", "rerun", "42")], calls


def test_ci_rerun_is_declared_mutating_and_a_capability() -> None:
    def toml(name: str) -> dict[str, Any]:
        loaded: dict[str, Any] = tomllib.loads((ROOT / name).read_text(encoding="utf-8"))
        return loaded

    assert "scripts/ci_rerun.py" in toml("mise.toml")["tasks"]["ci:rerun"]["run"]
    listed = toml("contracts/capabilities.toml")["capabilities"]
    found = [entry for entry in listed if entry["task"] == "ci:rerun"]
    expected = {
        "task": "ci:rerun",
        "version": "1.0.0",
        "implementation": "scripts/ci_rerun.py",
        "emits": "command-outcome/v1",
    }
    assert found == [expected], found
    assert "ci:rerun" not in toml("contracts/task-effects.toml")["read_only"], "it changes CI"
