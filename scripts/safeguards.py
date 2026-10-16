"""safeguards:prove -- every listed safeguard is proven by a test that kills its mutant (A.52).

A GUARD IS PROVEN BY WHAT BREAKS WITHOUT IT. Each safeguard names its engine and guard, one
mutation that disables exactly that guard (an anchor found once, and its replacement), and the
proof that must fail when the mutation is applied. A trial runs the proof three times: on the
repository as it is and on an unmutated scratch copy of its tracked files, both of which must
pass, since mutation testing on a failing baseline measures nothing; then on the copy with the
mutation applied. Only a proof that fails there kills the mutant. A proof that still passes lets
it survive; an error or a missing node is inconclusive and never counted as killed; a missing
proof or an anchor not found exactly once is refused before anything runs.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from contract_base import from_document
from gitenv import git
from junit_report import ReportError, load, node_of, outcome_of

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "contracts" / "safeguards.toml"

Verdict = Literal[
    "killed",
    "survived",
    "inconclusive",
    "baseline_failed",
    "mutation_invalid",
    "proof_missing",
]
RunProof = Callable[[Path, str], str]
Copy = Callable[[Path, Path], None]


class Safeguard(BaseModel):
    """One guard, the mutation that disables it, and the proof that must kill that mutation."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    engine: str
    guard: str
    path: str
    anchor: str
    mutant: str
    proof: str


class SafeguardsRegister(BaseModel):
    """safeguards-register/v1: every listed safeguard of the engines on this branch."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    contract: Literal["safeguards-register/v1"] = "safeguards-register/v1"
    safeguards: tuple[Safeguard, ...] = ()


class Trial(BaseModel):
    """What happened to one safeguard's mutant."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    verdict: Verdict
    detail: str


class TrialReport(BaseModel):
    """safeguards-trials/v1: every trial; only a report in which all are killed passes."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    contract: Literal["safeguards-trials/v1"] = "safeguards-trials/v1"
    trials: tuple[Trial, ...]


def copy_tracked(root: Path, destination: Path) -> None:
    """Copy every tracked file of root into destination, nothing untracked or ignored."""
    listed = git("ls-files", "-z", cwd=root)
    if listed.returncode != 0:
        raise SystemExit(f"git ls-files failed in {root}: {listed.stderr.strip()}")
    for name in filter(None, listed.stdout.split("\0")):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target)


def run_proof(base: Path, node: str) -> str:
    """How the named proof ended when run in base, from the JUnit report that run wrote."""
    with tempfile.TemporaryDirectory() as reports:
        report = Path(reports) / "proof.xml"
        started = time.time()
        argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        argv += ["--junitxml", str(report), node]
        subprocess.run(argv, cwd=base, check=False, capture_output=True)
        try:
            cases = load(report, started)
        except ReportError as problem:
            return f"error: {problem.detail}"
        found = [outcome_of(case) for case in cases if node_of(case) == node]
        return found[0] if found else "missing"


def trial(
    safeguard: Safeguard, root: Path, run: RunProof = run_proof, copy: Copy = copy_tracked
) -> Trial:
    """Baseline and control pass, then the mutant: killed only if the proof then fails."""

    def verdict(code: Verdict, detail: str) -> Trial:
        return Trial(id=safeguard.id, verdict=code, detail=detail)

    if not safeguard.proof:
        return verdict("proof_missing", "no proof is named")
    target = root / safeguard.path
    text = target.read_text(encoding="utf-8") if target.is_file() else ""
    if text.count(safeguard.anchor) != 1:
        return verdict("mutation_invalid", f"anchor found {text.count(safeguard.anchor)} times")
    baseline = run(root, safeguard.proof)
    if baseline != "passed":
        return verdict("baseline_failed", f"the proof is {baseline} before any mutation")
    with tempfile.TemporaryDirectory() as scratch:
        base = Path(scratch)
        copy(root, base)
        control = run(base, safeguard.proof)
        mutated = text.replace(safeguard.anchor, safeguard.mutant)
        (base / safeguard.path).write_text(mutated, encoding="utf-8")
        outcome = run(base, safeguard.proof)
    if control != "passed":
        return verdict("inconclusive", f"the unmutated copy gives {control}, so nothing is shown")
    if outcome == "passed":
        return verdict("survived", "the proof still passes with the guard disabled")
    if outcome != "failed":
        return verdict("inconclusive", f"the proof is {outcome} with the guard disabled")
    return verdict("killed", "the proof fails with the guard disabled")


def main() -> int:
    register = from_document(SafeguardsRegister, tomllib.loads(REGISTER.read_text("utf-8")))
    trials = tuple(trial(safeguard, ROOT) for safeguard in register.safeguards)
    print(TrialReport(trials=trials).model_dump_json(indent=2))
    return 0 if trials and all(t.verdict == "killed" for t in trials) else 2


if __name__ == "__main__":
    sys.exit(main())
