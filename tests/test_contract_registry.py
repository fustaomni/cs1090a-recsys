"""One contract per concept: one model per contract id, and decisions are decision/v1 (A.71)."""

from __future__ import annotations

from contract_registry import ROOT, contract_findings, decision_findings, sources, stale_exceptions

ONE = 'class A(Contract):\n    contract: Literal["probe/v1"] = "probe/v1"\n'
TWO = 'class B(Contract):\n    contract: Literal["probe/v1"] = "probe/v1"\n'
DRIFT = (
    'class C(Contract):\n    CONTRACT_ID: ClassVar[str] = "probe/v2"\n'
    '    contract: Literal["probe/v3"] = "probe/v3"\n'
)
ROLLED = "from plan_models import Decision\n\n\nclass R(Contract):\n    decision: Decision\n"
PROPER = (
    "from spine import Decision\n\n\nclass S(Contract):\n    decision: Decision | None = None\n"
)


def test_a_second_model_with_a_registered_contract_id_is_refused() -> None:
    assert contract_findings([("a.py", ONE), ("b.py", TWO), ("c.py", DRIFT)]) == [
        "probe/v1: declared by a.py::A, b.py::B",
        "c.py::C: CONTRACT_ID probe/v2 is not its contract",
    ]
    assert contract_findings(sources(ROOT)) == []


def test_only_decision_v1_may_carry_a_decision() -> None:
    assert decision_findings([("r.py", ROLLED), ("s.py", PROPER)]) == [
        "r.py:5: decision is not decision/v1"
    ]
    assert decision_findings(sources(ROOT)) == []


LISTED = 'class Readiness(Contract):\n    decision: Literal["wait", "merge", "refuse"]\n'


def test_a_listed_decision_passes_only_where_it_is_listed() -> None:
    """A.19: merge.readiness's answer passes in pr.Readiness, and nowhere else."""
    assert decision_findings([("scripts/pr.py", LISTED)]) == []
    assert decision_findings([("scripts/other.py", LISTED)]) == [
        "scripts/other.py:2: decision is not decision/v1"
    ]


def test_an_exception_that_matches_nothing_is_stale() -> None:
    """A.19: an exception whose field is gone is reported, so none outlives its code."""
    assert stale_exceptions([("scripts/pr.py", PROPER)]) == ["scripts/pr.py::Readiness.decision"]
    assert stale_exceptions(sources(ROOT)) == []
