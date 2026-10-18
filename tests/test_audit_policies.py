"""Each runs.models and runs.evidence guard, judged through its policy alone (A.107).

cscie103 proves these audits through their Python observers, which a mutant in the policy never
reaches. Each proof here builds its inventory directly and evaluates the policy, so every guard
has a proof that fails when that guard is removed.
"""

from __future__ import annotations

import evidence_audit
import model_audit
import spine


def _models(inventory: model_audit.ModelInventory, subject: str = "models") -> set[str]:
    found = spine.evaluate(inventory, subject, model_audit.POLICY, model_audit.ENTRYPOINT)
    return {rule.code for rule in found.rules if rule.outcome == "fail"}


def _evidence(inventory: evidence_audit.EvidenceInventory, subject: str = "evidence") -> set[str]:
    policy, entrypoint = evidence_audit.POLICY, evidence_audit.ENTRYPOINT
    found = spine.evaluate(inventory, subject, policy, entrypoint)
    return {rule.code for rule in found.rules if rule.outcome == "fail"}


def _model_inventory(
    *findings: model_audit.ModelFinding, scanned: int = 1
) -> model_audit.ModelInventory:
    return model_audit.ModelInventory(files_scanned=scanned, direct=(), findings=findings)


def _evidence_inventory(
    *findings: evidence_audit.EvidenceFinding, contracts: tuple[str, ...] = ("Probe",)
) -> evidence_audit.EvidenceInventory:
    return evidence_audit.EvidenceInventory(files_scanned=1, contracts=contracts, findings=findings)


def test_an_unobserved_model_inventory_is_refused_by_the_policy() -> None:
    assert "ERR_MODELS_INPUT_MISSING" in _models(_model_inventory(), "not_models")


def test_a_model_audit_that_scanned_nothing_is_refused_by_the_policy() -> None:
    assert "ERR_MODELS_NOTHING_SCANNED" in _models(_model_inventory(scanned=0))
    assert "ERR_MODELS_NOTHING_SCANNED" not in _models(_model_inventory())


def test_an_unbaselined_model_is_refused_by_the_policy() -> None:
    finding = model_audit.ModelFinding(entry="scripts/probe.py::Probe", kind="unbaselined")
    assert "ERR_MODELS_UNBASELINED" in _models(_model_inventory(finding))


def test_a_stale_baseline_entry_is_refused_by_the_policy() -> None:
    finding = model_audit.ModelFinding(entry="scripts/probe.py::Probe", kind="stale")
    assert "ERR_MODELS_STALE" in _models(_model_inventory(finding))


def test_an_unobserved_evidence_inventory_is_refused_by_the_policy() -> None:
    assert "ERR_EVIDENCE_INPUT_MISSING" in _evidence(_evidence_inventory(), "not_evidence")


def test_an_evidence_audit_that_found_no_contract_is_refused_by_the_policy() -> None:
    assert "ERR_EVIDENCE_NONE_FOUND" in _evidence(_evidence_inventory(contracts=()))
    assert "ERR_EVIDENCE_NONE_FOUND" not in _evidence(_evidence_inventory())


def test_an_unresolved_evidence_argument_is_refused_by_the_policy() -> None:
    finding = evidence_audit.EvidenceFinding(
        path="scripts/probe.py", line=1, contract="probe", field="", kind="unresolved"
    )
    assert "ERR_EVIDENCE_UNRESOLVED" in _evidence(_evidence_inventory(finding))
