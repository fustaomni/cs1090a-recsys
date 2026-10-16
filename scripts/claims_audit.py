"""Pillars and assessment claims are credited only with evidence (A.36).

A PILLAR IS CREDITED BY WHAT IT DID, NOT BY A FILE'S NAME. Each pillar names the contract that
defines it, the task that produces it, the proofs that fail when it breaks, and the run ids of
recorded runs in which that task passed. The audit checks every one: the contract is a file, the
task is declared, each proof is a module-level test, and each run is in the hash-chained ledger,
by that task, passing. A ledger whose chain is broken credits nothing.

A CLAIM IS KEPT WITH ITS VERDICT. Assessment claims stay in the register whatever their fate:
held, partly held, agreed or refuted, each naming the findings that decide it. A credit that a
recorded finding contradicts must be entered as refuted or partly held, and a refutation must
name the finding that refutes it, so a later summary cannot quietly overturn the record.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from contract_base import from_document
from run_ledger import RunRecord, default_ledger, verify
from run_task import declared_tasks

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "contracts" / "claims.toml"

FindingId = Annotated[str, Field(pattern=r"^C[0-9]+$")]


class Pillar(BaseModel):
    """A pillar: its contract, the task producing it, its proofs, and runs where it acted."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    name: str
    contract: str
    task: str
    proofs: tuple[str, ...]
    runs: tuple[str, ...] = ()


class Claim(BaseModel):
    """An assessment claim and the verdict the register's findings reach on it."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    source: FindingId
    claim: str
    verdict: Literal["held", "partly_held", "agreed", "refuted"]
    decided_by: tuple[FindingId, ...] = Field(min_length=1)
    contradicted_by: tuple[FindingId, ...] = ()


class ClaimsRegister(BaseModel):
    """claims-register/v1: the pillars and the assessment claims, each with its evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    contract: Literal["claims-register/v1"] = "claims-register/v1"
    pillars: tuple[Pillar, ...] = ()
    claims: tuple[Claim, ...] = ()


FindingCode = Literal[
    "PILLAR_CONTRACT_MISSING",
    "PILLAR_TASK_UNDECLARED",
    "PILLAR_PROOF_MISSING",
    "PILLAR_WITHOUT_RUN",
    "PILLAR_RUN_NOT_FOUND",
    "PILLAR_RUN_NOT_PASSING",
    "CLAIM_ID_DUPLICATE",
    "CLAIM_CONTRADICTED_CREDIT",
    "CLAIM_REFUTED_WITHOUT_FINDING",
]


class Finding(BaseModel):
    """One reason the register does not hold, against one pillar or claim."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    code: FindingCode
    subject: str
    detail: str


class AuditReport(BaseModel):
    """claims-audit/v1: how much was audited, and every finding; none is the only pass."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    contract: Literal["claims-audit/v1"] = "claims-audit/v1"
    pillars: int
    claims: int
    findings: tuple[Finding, ...]


def _defines(test_file: Path, name: str) -> bool:
    if not test_file.is_file():
        return False
    tree = ast.parse(test_file.read_text(encoding="utf-8"))
    return any(isinstance(node, ast.FunctionDef) and node.name == name for node in tree.body)


def _pillar_findings(
    pillar: Pillar, root: Path, runs: dict[str, tuple[str, str]], declared: frozenset[str]
) -> list[Finding]:
    found: list[Finding] = []

    def add(code: FindingCode, detail: str) -> None:
        found.append(Finding(code=code, subject=pillar.name, detail=detail))

    if not (root / pillar.contract).is_file():
        add("PILLAR_CONTRACT_MISSING", f"{pillar.contract} is not a file")
    if pillar.task not in declared:
        add("PILLAR_TASK_UNDECLARED", f"{pillar.task} is not a declared task")
    if not pillar.proofs:
        add("PILLAR_PROOF_MISSING", "no proof is named")
    for proof in pillar.proofs:
        path, _, name = proof.partition("::")
        if not _defines(root / path, name):
            add("PILLAR_PROOF_MISSING", f"{proof} is not defined")
    if not pillar.runs:
        add("PILLAR_WITHOUT_RUN", "no recorded run shows it acting")
    for run_id in pillar.runs:
        if run_id not in runs:
            add("PILLAR_RUN_NOT_FOUND", f"run {run_id} is not in the ledger")
        elif runs[run_id] != (pillar.task, "pass"):
            add("PILLAR_RUN_NOT_PASSING", f"run {run_id} was {runs[run_id]}")
    return found


def _claim_findings(claim: Claim) -> list[Finding]:
    if claim.verdict in ("held", "agreed") and claim.contradicted_by:
        detail = "credited although contradicted by " + ", ".join(claim.contradicted_by)
        return [Finding(code="CLAIM_CONTRADICTED_CREDIT", subject=claim.id, detail=detail)]
    if claim.verdict == "refuted" and not claim.contradicted_by:
        detail = "refuted without naming the finding that refutes it"
        return [Finding(code="CLAIM_REFUTED_WITHOUT_FINDING", subject=claim.id, detail=detail)]
    return []


def audit(
    register: ClaimsRegister,
    root: Path,
    runs: dict[str, tuple[str, str]],
    declared: frozenset[str],
) -> list[Finding]:
    """Every finding against the register; an empty list is the only passing audit."""
    found: list[Finding] = []
    for pillar in register.pillars:
        found += _pillar_findings(pillar, root, runs, declared)
    seen: set[str] = set()
    for claim in register.claims:
        if claim.id in seen:
            found.append(Finding(code="CLAIM_ID_DUPLICATE", subject=claim.id, detail="id reused"))
        seen.add(claim.id)
        found += _claim_findings(claim)
    return found


def _ledger_runs(path: Path) -> dict[str, tuple[str, str]]:
    """Every recorded run's task and verdict, from a ledger whose chain holds."""
    report = verify(path)
    if not report.intact:
        raise SystemExit(f"ledger chain breaks at record {report.broken_at}; nothing credited")
    runs: dict[str, tuple[str, str]] = {}
    if not path.exists():
        return runs
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = RunRecord.model_validate_json(line)
            runs[record.run_id] = (record.task, record.verdict)
    return runs


def main() -> int:
    register = from_document(ClaimsRegister, tomllib.loads(REGISTER.read_text(encoding="utf-8")))
    found = audit(register, ROOT, _ledger_runs(default_ledger()), declared_tasks())
    report = AuditReport(
        pillars=len(register.pillars), claims=len(register.claims), findings=tuple(found)
    )
    print(report.model_dump_json(indent=2))
    return 0 if not found else 2


if __name__ == "__main__":
    sys.exit(main())
