"""Each runs.mutation guard cscie103 proves only end to end, judged through its policy alone.

cscie103's harness proofs reach the policy through real killers in scratch projects, and cover
the baseline, the anchor and a survivor. The other four guards are proven here: each builds the
evidence from the harness's own models, flips one observation, and evaluates the policy.
"""

from __future__ import annotations

import mutation_check
import spine


def _run(exit_code: int) -> mutation_check.KillerRun:
    return mutation_check.KillerRun(
        test="tests/test_probe.py::test_probe",
        exit_code=exit_code,
        duration_seconds=0.1,
        output_sha256="0" * 64,
    )


def _evidence(
    *, listed: bool = True, untouched: bool = True, killer_exit: int = 1
) -> mutation_check.MutationEvidence:
    mutant = mutation_check.MutantEvidence(
        id="probe", file="scripts/probe.py", anchor_found_once=True, runs=(_run(killer_exit),)
    )
    return mutation_check.MutationEvidence(
        tree_listed=listed, baseline=(_run(0),), mutants=(mutant,), tree_untouched=untouched
    )


def _failing(evidence: mutation_check.MutationEvidence, subject: str = "mutation") -> set[str]:
    found = spine.evaluate(evidence, subject, mutation_check.POLICY, mutation_check.ENTRYPOINT)
    return {rule.code for rule in found.rules if rule.outcome == "fail"}


def test_an_unobserved_mutation_run_is_refused_by_the_policy() -> None:
    assert "ERR_MUTATION_INPUT_MISSING" in _failing(_evidence(), "not_mutation")


def test_an_unlisted_tree_is_refused_by_the_policy() -> None:
    assert "ERR_MUTATION_TREE_UNLISTED" in _failing(_evidence(listed=False))
    assert "ERR_MUTATION_TREE_UNLISTED" not in _failing(_evidence())


def test_an_unjudged_killer_is_refused_by_the_policy() -> None:
    assert "ERR_MUTATION_KILLER_UNJUDGED" in _failing(_evidence(killer_exit=-1))
    assert "ERR_MUTATION_KILLER_UNJUDGED" not in _failing(_evidence())


def test_a_touched_tree_is_refused_by_the_policy() -> None:
    assert "ERR_MUTATION_TREE_TOUCHED" in _failing(_evidence(untouched=False))
    assert "ERR_MUTATION_TREE_TOUCHED" not in _failing(_evidence())
