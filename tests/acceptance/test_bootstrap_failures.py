# tests/acceptance/test_bootstrap_failures.py
"""Case 1, the first red: no gate failure is ever reported as success (register 2, 13).

env:bootstrap runs its gates in order. Each case injects one fault at the operating-system
boundary of a sandboxed copy -- a file or a permission, never a hook in production code --
and asserts what the register requires: a non-zero exit, no success, the failing gate named
with its class, the true exit code and the input digests, no later gate run, and a ledger
record. env:bootstrap is implemented in H1; until then every case is a strict expected
failure, so the first to pass fails the suite until its marker leaves with the change.
"""

from __future__ import annotations

import json
import stat
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from acceptance_sandbox import GatewayRun, Sandbox

from command_outcome import CommandOutcome
from run_task import _declared

NEWLINE = chr(10)
GATES = (
    "request_validation",
    "configuration_read",
    "policy_evaluation",
    "tool_install",
    "dependency_sync",
    "test_run",
    "evidence_write",
)

pytestmark = pytest.mark.acceptance

Fault = Callable[[Sandbox], tuple[str, ...]]


class CapabilityAbsentError(Exception):
    """The red's intended reason: the gateway does not declare the task under test."""


def _require(sandbox: Sandbox, task: str) -> None:
    if task not in _declared(sandbox.root):
        raise CapabilityAbsentError(f"{task} is not declared in mise.toml yet")


def _flip_first_digest(path: Path) -> None:
    """Change one hex digit of the first sha256 digest: an integrity fault (case 103)."""
    text = path.read_text(encoding="utf-8")
    at = text.index("sha256:") + len("sha256:")
    replacement = "0" if text[at] != "0" else "1"
    path.write_text(text[:at] + replacement + text[at + 1 :], encoding="utf-8")


def _bad_request(sandbox: Sandbox) -> tuple[str, ...]:
    return ("--revision", "not-a-revision")


def _unreadable_configuration(sandbox: Sandbox) -> tuple[str, ...]:
    path = sandbox.root / "pyproject.toml"
    path.write_text(path.read_text(encoding="utf-8") + "[[[" + NEWLINE, encoding="utf-8")
    return ()


def _uncompilable_policy(sandbox: Sandbox) -> tuple[str, ...]:
    planted = sandbox.root / "policies" / "planted" / "broken.rego"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text(NEWLINE.join(("package planted", "deny contains")) + NEWLINE)
    return ()


def _tampered_tool_lock(sandbox: Sandbox) -> tuple[str, ...]:
    _flip_first_digest(sandbox.root / "mise.lock")
    return ()


def _tampered_dependency_lock(sandbox: Sandbox) -> tuple[str, ...]:
    _flip_first_digest(sandbox.root / "uv.lock")
    return ()


def _failing_test(sandbox: Sandbox) -> tuple[str, ...]:
    planted = sandbox.root / "tests" / "test_planted_failure.py"
    planted.write_text(NEWLINE.join(("def test_planted() -> None:", "    assert False")) + NEWLINE)
    return ()


def _unwritable_evidence(sandbox: Sandbox) -> tuple[str, ...]:
    evidence = sandbox.root / ".artifacts" / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    evidence.chmod(stat.S_IRUSR | stat.S_IXUSR)
    return ()


FAULTS: dict[str, Fault] = {
    "request_validation": _bad_request,
    "configuration_read": _unreadable_configuration,
    "policy_evaluation": _uncompilable_policy,
    "tool_install": _tampered_tool_lock,
    "dependency_sync": _tampered_dependency_lock,
    "test_run": _failing_test,
    "evidence_write": _unwritable_evidence,
}


@pytest.fixture(name="sandbox")
def _sandbox(tmp_path: Path) -> Iterator[Sandbox]:
    made = Sandbox.create(tmp_path)
    yield made
    made.restore_permissions()
    evidence = made.root / ".artifacts" / "evidence"
    if evidence.is_dir():
        evidence.chmod(stat.S_IRWXU)


def _outcome(run: GatewayRun) -> CommandOutcome:
    """The last command-outcome/v1 document the run printed, validated by its own model."""
    decoder = json.JSONDecoder()
    found: list[CommandOutcome] = []
    at = run.stdout.find("{")
    while at != -1:
        try:
            value, end = decoder.raw_decode(run.stdout, at)
        except json.JSONDecodeError:
            at = run.stdout.find("{", at + 1)
            continue
        if isinstance(value, dict) and value.get("contract") == "command-outcome/v1":
            found.append(CommandOutcome.model_validate(value))
        at = run.stdout.find("{", end)
    if not found:
        raise AssertionError("no command-outcome/v1 was printed:" + NEWLINE + run.output[-2000:])
    return found[-1]


def test_the_catalog_names_every_gate_once() -> None:
    assert tuple(FAULTS) == GATES, FAULTS


@pytest.mark.xfail(
    raises=CapabilityAbsentError,
    reason="env:bootstrap is implemented in H1 (register 2, 13)",
    strict=True,
)
@pytest.mark.parametrize("gate", GATES)
def test_no_gate_failure_reports_success(sandbox: Sandbox, gate: str) -> None:
    _require(sandbox, "env:bootstrap")
    arguments = FAULTS[gate](sandbox)
    run = sandbox.gateway("env:bootstrap", *arguments)
    assert run.exit_code != 0, run.output[-2000:]
    outcome = _outcome(run)
    assert outcome.outcome != "success", outcome
    assert outcome.code != "applied", outcome
    assert outcome.data.get("failed_gate") == gate, outcome
    assert outcome.data.get("not_run") == list(GATES[GATES.index(gate) + 1 :]), outcome
    assert isinstance(outcome.data.get("failure_class"), str), outcome
    assert outcome.data.get("exit_code") == run.exit_code, outcome
    digests = outcome.data.get("input_digests")
    assert isinstance(digests, dict) and digests, outcome
    assert any(record.task == "env:bootstrap" for record in sandbox.ledger_records()), run.output
