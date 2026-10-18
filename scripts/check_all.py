"""Run every gate, report every result, exit nonzero if any failed.

THE PROBLEM THIS REPLACES
`check` was a mise task with depends = [lint, types, test, ...]. mise runs
dependencies in PARALLEL, up to four jobs, with no order among them, and reports
failure as soon as one fails. The observed effect: `test` failed at 1.4s and
`types` never reported at all -- mypy was still running and nobody was listening.

That produces fix-one, re-run, discover-the-next: a treadmill built into the gate
itself. Worse, a task whose result is never printed is indistinguishable from one
that passed, so the gate can quietly under-report what it checked.

WHAT THIS DOES INSTEAD
Runs each gate to completion, captures its output, and prints a summary of ALL
results. Same contract as `pre-commit run --all-files`: one invocation tells the
whole truth. Serial and slower, deliberately -- correctness of reporting beats
a few seconds on a gate that runs on every commit.

WHY EACH GATE IS STILL ITS OWN mise TASK
So `mise run lint` works standalone during iteration. This aggregates them; it
does not replace them, and there is no second copy of the list to drift.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, model_validator

from bounded import Exited, TimedOut, run
from contract_base import Contract

State = Literal["executed_passed", "executed_failed", "timed_out", "reused", "nothing_to_run"]

# pytest's ExitCode.NO_TESTS_COLLECTED: nothing was selected, so nothing ran (A.90).
NO_TESTS_COLLECTED = 5


class GateSpec(Contract):
    """One gate, declared: its command, whether the hooks run it, and its deadline (D.176, R2)."""

    name: str = Field(min_length=1)
    command: tuple[str, ...] = Field(min_length=1)
    runs_in_hooks: bool
    timeout_seconds: float = Field(gt=0)
    # A LANE MAY DECLARE ITSELF EMPTY (A.90): only then is pytest's exit 5 nothing to run.
    may_be_empty: bool = False
    # A CLAIM ABOUT THE DEVELOPER MACHINE (A.104) is declared out of CI: the runner is not it.
    runs_in_ci: bool = True


class GateRun(Contract):
    """How one gate ended (R3): executed and passed or failed, timed out, or reused."""

    name: str
    state: State
    duration_seconds: float
    output: str
    provenance: str | None = None

    @model_validator(mode="after")
    def _reuse_names_its_source(self) -> GateRun:
        if (self.state == "reused") != (self.provenance is not None):
            raise ValueError("a reused gate names its provenance, and only a reused gate has one")
        return self

    @property
    def passed(self) -> bool:
        """Only an executed pass or a reused one; a timeout never passes."""
        return self.state in ("executed_passed", "reused")


class GateReport(Contract):
    """gate-report/v1: every gate run of one check, written with --report for a caller (D.178)."""

    CONTRACT_ID: ClassVar[str] = "gate-report/v1"

    contract: Literal["gate-report/v1"] = "gate-report/v1"
    gates: tuple[GateRun, ...]


# ONE LIST, TWO MODES. Each gate declares whether it needs the network.
#
# WHY NOT TWO LISTS: hooks must be fast and must work offline, CI must be
# exhaustive. Writing that as two sets of checks in two places is precisely the
# drift this repo exists to prevent -- add a gate to one, forget the other, and
# the difference is invisible until something ships broken. A flag over a single
# list cannot drift.
#
# Order is presentation order, not dependency order; every selected gate runs
# regardless of whether an earlier one failed.
#
# WHY ONE SERIAL RUNNER RATHER THAN PARALLEL CI JOBS.
# A matrix fanning these into separate jobs would give per-gate check names that
# branch protection could require individually, and failure attribution visible
# from the check list rather than the log. Both are real advantages, and both
# are rejected on one ground: a matrix must ENUMERATE the gates in YAML, making
# ci.yml a second source of truth for this list. That copy goes stale silently,
# which is the drift the whole design avoids -- ci.yml runs `mise run check` and
# restates nothing.
#
# Running everything and reporting everything is also the right choice for a
# QUALITY gate specifically: fail-fast minimises wasted work after a decisive
# failure, while running all checks maximises the diagnostic information from
# one commit. A gate wants the second.
#
# EACH GATE IS A GateSpec (D.176, R2): its command, whether the hooks run it, and a deadline
# sized loosely from its observed runtime, so a hung gate ends as timed_out, never as a pass.
#
# runs_in_hooks=False means "CI only": either it needs the network and valid
# Databricks auth, or it is slow enough that including it would train people to
# bypass the hook. Both make a gate that belongs in CI, where a bypass is caught.
# WITHDRAWN IN THE PORT (recsys founding F7, plan A.3): cscie103's registry named gates whose
# script, task or tool recsys does not have, so the pre-push gate failed closed on gates that
# could never run. Each returns with its script or tool; until then it is named, not skipped.
# Hooks: policy, policy decisions, repo hygiene,
# assertions, evidence, models, mutation anchors,
# schemas, nix contract. CI-only: pii, fixtures, prereqs, env-parity, nix flake.
GATES: tuple[GateSpec, ...] = (
    GateSpec(
        name="lint",
        command=("uv", "run", "ruff", "check", "--no-cache", "."),
        runs_in_hooks=True,
        timeout_seconds=300.0,
    ),
    GateSpec(
        name="format",
        command=("uv", "run", "ruff", "format", "--check", "."),
        runs_in_hooks=True,
        timeout_seconds=300.0,
    ),
    # BOTH PLATFORMS, DELIBERATELY. mypy defaults to the OS it runs on and
    # NARROWS sys.platform comparisons, so a Darwin-only branch is invisible to a
    # Linux run and vice versa. This repo is a macOS laptop plus a Linux CI
    # runner; checking one leaves the other branch unverified everywhere.
    GateSpec(
        name="types (darwin)",
        command=("uv", "run", "mypy", "--platform", "darwin"),
        runs_in_hooks=True,
        timeout_seconds=300.0,
    ),
    GateSpec(
        name="types (linux)",
        command=("uv", "run", "mypy", "--platform", "linux"),
        runs_in_hooks=True,
        timeout_seconds=300.0,
    ),
    GateSpec(
        name="test",
        command=("uv", "run", "pytest", "-q"),
        runs_in_hooks=True,
        timeout_seconds=900.0,
    ),
    # FULL HISTORY, NOT THE WORKING TREE. A pre-commit hook only ever sees the
    # incoming change, so anything committed before hooks existed -- or pushed
    # with --no-verify -- has never been scanned. This repo already leaked an
    # OAuth secret to a terminal; the credential never reached a commit, but the
    # class of mistake did happen here.
    #
    # betterleaks rather than gitleaks: same author, MIT, drop-in, and gitleaks
    # now receives security patches only. It replaces Shannon entropy with token
    # efficiency scoring, which raises precision substantially -- precision
    # matters as much as recall, because a scanner that cries wolf trains people
    # to bypass it, which is how the gate really fails.
    #
    # --redact keeps any finding out of CI logs, where it would become a second
    # leak in the process of reporting the first.
    GateSpec(
        name="secrets (history)",
        command=("betterleaks", "git", "--redact", "--no-banner"),
        runs_in_hooks=True,
        timeout_seconds=300.0,
    ),
    # THE WORKFLOW'S OWN CLAIMS, ENFORCED (D.84). ci.yml pins every action to a commit
    # SHA and grants the token contents: read; zizmor sat in the devShell and no gate
    # ran it, so nothing stopped an edit from making either claim false. PEDANTIC,
    # OBSERVED: the default persona suppressed a write-all probe ("3 suppressed"),
    # pedantic flagged it, and this repository's workflows are clean under it.
    # Offline and sub-second, so the hooks run it too.
    GateSpec(
        name="workflows",
        command=("uv", "run", "python", "scripts/workflow_audit.py"),
        runs_in_hooks=True,
        timeout_seconds=300.0,
    ),
    # EXEMPTIONS LAPSE (D.174, R55.4): an expired one, or one naming a path that is gone, fails.
    GateSpec(
        name="exemptions",
        command=("uv", "run", "python", "scripts/exemptions.py"),
        runs_in_hooks=True,
        timeout_seconds=300.0,
    ),
    # INLINE SUPPRESSIONS ARE PERMISSIONS (D.219, R55.4): one with no live exemption fails.
    GateSpec(
        name="suppressions",
        command=("uv", "run", "python", "scripts/suppression_audit.py"),
        runs_in_hooks=True,
        timeout_seconds=300.0,
    ),
    # ONE REGISTRY OF PROBLEM CODES (D.177, R60): unregistered, repurposed or prose fails.
    GateSpec(
        name="problems",
        command=("uv", "run", "python", "scripts/problem_codes.py"),
        runs_in_hooks=True,
        timeout_seconds=300.0,
    ),
    # The integration-marked tests, deselected from the hermetic `test` gate.
    GateSpec(
        name="test (integration)",
        command=("uv", "run", "pytest", "-m", "integration"),
        runs_in_hooks=False,
        may_be_empty=True,
        timeout_seconds=1200.0,
    ),
    # CLAIMS ABOUT THIS MACHINE (A.104): A.8's proofs that its mise state and new files are
    # owner-only. The hooks and the snapshot before every publication run them here; CI's
    # runner is not this machine, so the gate is declared out of CI, never detected there.
    GateSpec(
        name="test (machine)",
        command=("uv", "run", "pytest", "-m", "machine"),
        runs_in_hooks=True,
        runs_in_ci=False,
        timeout_seconds=300.0,
    ),
)


def selected(specs: tuple[GateSpec, ...], *, hooks: bool, ci: bool = False) -> tuple[GateSpec, ...]:
    """The gates to run: all, the hooks' own, or on CI all but claims about this machine (R2)."""
    return tuple(
        spec for spec in specs if (spec.runs_in_hooks or not hooks) and (spec.runs_in_ci or not ci)
    )


def run_gate(spec: GateSpec) -> GateRun:
    """Run one gate under its own deadline; a timeout is its own state, never a pass (R2, R3)."""
    started = time.monotonic()
    result = run(list(spec.command), deadline=spec.timeout_seconds, cwd=Path.cwd())
    ended = result.termination
    if isinstance(ended, TimedOut):
        state: State = "timed_out"
    elif isinstance(ended, Exited) and ended.code == 0:
        state = "executed_passed"
    elif isinstance(ended, Exited) and ended.code == NO_TESTS_COLLECTED and spec.may_be_empty:
        state = "nothing_to_run"
    else:
        state = "executed_failed"
    return GateRun(
        name=spec.name,
        state=state,
        duration_seconds=round(time.monotonic() - started, 3),
        output=(result.stdout + result.stderr).strip(),
    )


def _report_path(argv: list[str]) -> Path | None:
    """--report <path>: where the typed runs are written, beside the printed summary."""
    if "--report" not in argv[:-1]:
        return None
    return Path(argv[argv.index("--report") + 1])


def main() -> int:
    offline = "--offline" in sys.argv
    on_ci = "--ci" in sys.argv
    gates = selected(GATES, hooks=offline, ci=on_ci)
    if on_ci:
        omitted = ", ".join(spec.name for spec in GATES if not spec.runs_in_ci)
        print(f"not run on CI, by declaration: {omitted}", flush=True)

    if offline:
        skipped = [spec.name for spec in GATES if not spec.runs_in_hooks]
        print(f"offline mode: skipping {', '.join(skipped)}\n")

    runs: list[GateRun] = []

    for spec in gates:
        ran = run_gate(spec)
        runs.append(ran)
        late = f" (timed out after {spec.timeout_seconds:g}s)" if ran.state == "timed_out" else ""
        label = "NONE" if ran.state == "nothing_to_run" else "PASS" if ran.passed else "FAIL"
        print(f"{label}  {spec.name}{late}", flush=True)

    report = _report_path(sys.argv)
    if report is not None:
        report.write_text(GateReport(gates=tuple(runs)).model_dump_json(), encoding="utf-8")

    failed = [ran for ran in runs if not ran.passed and ran.state != "nothing_to_run"]

    if failed:
        for ran in failed:
            print(f"\n{'=' * 70}\nFAILED: {ran.name}\n{'=' * 70}", file=sys.stderr)
            print(ran.output, file=sys.stderr)
        print(
            f"\n{len(failed)} of {len(runs)} gates failed: {', '.join(ran.name for ran in failed)}",
            file=sys.stderr,
        )
        return 1

    empty = [ran.name for ran in runs if ran.state == "nothing_to_run"]
    note = f"; nothing to run in {', '.join(empty)}" if empty else ""
    print(f"\nall {len(runs) - len(empty)} gates passed{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
