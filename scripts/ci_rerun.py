# scripts/ci_rerun.py
"""ci:rerun -- one retry of a CI run GitHub never started a job for (A.265)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pydantic import Field

from command_outcome import CommandOutcome
from contract_base import Reading
from gitenv import git

ROOT = Path(__file__).resolve().parent.parent
# THE CONCLUSIONS OF A FINISHED FAILURE, as pr_logs.NOT_SUCCESSFUL names them.
ENDED_BADLY = frozenset(("failure", "cancelled", "timed_out", "startup_failure"))
VIEW = "databaseId,headSha,status,conclusion,attempt,jobs"


def _gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


class _Step(Reading):
    name: str
    conclusion: str | None = None


class _Job(Reading):
    database_id: int = Field(alias="databaseId")
    name: str
    conclusion: str | None = None
    steps: tuple[_Step, ...] = ()


class _Run(Reading):
    """gh run view --json: one run, its attempt, and each job with the steps it ran."""

    database_id: int = Field(alias="databaseId")
    head_sha: str = Field(alias="headSha")
    status: str
    conclusion: str | None = None
    attempt: int
    jobs: tuple[_Job, ...] = ()


def _view(run_id: str) -> _Run:
    return _Run.model_validate_json(_gh("run", "view", run_id, "--json", VIEW))


def refusal(run: _Run, head: str) -> str | None:
    """Why this run may not be retried, or None when only the platform failed it."""
    if run.head_sha != head:
        return f"run {run.database_id} is for {run.head_sha[:12]}, not this head {head[:12]}"
    if run.status != "completed" or run.conclusion not in ENDED_BADLY:
        return f"run {run.database_id} is {run.status}, {run.conclusion}: not a finished failure"
    ran = [job.name for job in run.jobs if job.steps]
    if ran:
        return f"run {run.database_id} ran steps in {', '.join(ran)}: the code failed, not CI"
    return None


def main(argv: list[str] | None = None) -> int:
    """ci:rerun <run-id> -- one retry of a run that never ran a step, read back."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not args[0].isdigit():
        raise SystemExit("usage: ci_rerun.py <run-id>")
    run_id = args[0]
    head = git("rev-parse", "HEAD", cwd=ROOT).stdout.strip()
    before = _view(run_id)
    reason = refusal(before, head)
    if reason is not None:
        verdict, code, message, attempt = "refused", "rerun_refused", reason, before.attempt
    else:
        _gh("run", "rerun", run_id)
        attempt = _view(run_id).attempt
        if attempt > before.attempt:
            verdict, code = "success", "rerun_requested"
            message = f"run {run_id}: attempt {attempt} requested on {head[:12]}"
        else:
            verdict, code = "failed", "rerun_not_started"
            message = f"run {run_id} reported no new attempt after the retry"
    outcome = CommandOutcome.model_validate(
        {
            "command": "ci:rerun",
            "outcome": verdict,
            "code": code,
            "message": message,
            "data": {"run_id": int(run_id), "head_sha": head, "attempt": attempt},
        }
    )
    print(json.dumps(outcome.model_dump(), indent=2))
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
