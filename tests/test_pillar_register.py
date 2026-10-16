"""Pillars and claims are credited only with evidence (A.36).

A pillar needs its contract, task, proofs and a passing recorded run of that task; a claim that a
recorded finding contradicts cannot stand as a credit. Every proof uses a scratch root.
"""

from __future__ import annotations

from pathlib import Path

from claims_audit import Claim, ClaimsRegister, Pillar, audit

RUN = "a" * 32


def _pillar(tmp_path: Path, runs: tuple[str, ...]) -> Pillar:
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "widget.py").write_text("WIDGET = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir(exist_ok=True)
    proof = "def test_widget_works() -> None:\n    assert True\n"
    (tmp_path / "tests" / "test_widget.py").write_text(proof, encoding="utf-8")
    return Pillar(
        name="widget",
        contract="scripts/widget.py",
        task="widget:run",
        proofs=("tests/test_widget.py::test_widget_works",),
        runs=runs,
    )


def _codes(register: ClaimsRegister, root: Path, runs: dict[str, tuple[str, str]]) -> set[str]:
    return {finding.code for finding in audit(register, root, runs, frozenset({"widget:run"}))}


def test_a_pillar_without_run_evidence_is_refused(tmp_path: Path) -> None:
    unproven = ClaimsRegister(pillars=(_pillar(tmp_path, ()),))
    assert _codes(unproven, tmp_path, {}) == {"PILLAR_WITHOUT_RUN"}
    unknown = ClaimsRegister(pillars=(_pillar(tmp_path, (RUN,)),))
    assert _codes(unknown, tmp_path, {}) == {"PILLAR_RUN_NOT_FOUND"}
    assert _codes(unknown, tmp_path, {RUN: ("widget:run", "fail")}) == {"PILLAR_RUN_NOT_PASSING"}
    assert _codes(unknown, tmp_path, {RUN: ("widget:run", "pass")}) == set()


def test_a_credit_contradicting_a_recorded_finding_is_refuted(tmp_path: Path) -> None:
    credit = Claim(
        id="C21.3",
        source="C21",
        claim="a missing module is a red that prevents false passes",
        verdict="held",
        decided_by=("C2",),
        contradicted_by=("C2",),
    )
    register = ClaimsRegister(claims=(credit,))
    assert _codes(register, tmp_path, {}) == {"CLAIM_CONTRADICTED_CREDIT"}
    refuted = ClaimsRegister(claims=(credit.model_copy(update={"verdict": "refuted"}),))
    assert _codes(refuted, tmp_path, {}) == set()
