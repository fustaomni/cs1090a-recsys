# tests/test_check_ruleset.py
"""check:ruleset judges the live ruleset on the spine (D.168).

ONLY gh IS REPLACED, and by an injected function rather than a global patch: the
observation, the readings, opa's verdict and the exit code are all real.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

import pytest

import spine
from check_ruleset import ENTRYPOINT, LISTING, POLICY, PRODUCER, main, observe

Answers = dict[str, str | None]


def _ruleset(*, pinned: int | None = 15368, strict: bool = True) -> str:
    check: dict[str, object] = {"context": "quality gate"}
    if pinned is not None:
        check["integration_id"] = pinned
    return json.dumps(
        {
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/develop", "refs/heads/main"]}},
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {"type": "pull_request", "parameters": {"allowed_merge_methods": ["merge"]}},
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "strict_required_status_checks_policy": strict,
                        "required_status_checks": [check],
                    },
                },
            ],
        }
    )


def _graph(count: int) -> str:
    node = {"name": "develop-and-main-protection", "bypassActors": {"totalCount": count}}
    return json.dumps({"data": {"repository": {"rulesets": {"nodes": [node]}}}})


def _answers(changes: Answers | None = None) -> Answers:
    answers: Answers = {
        LISTING: json.dumps([{"id": 7, "name": "develop-and-main-protection"}]),
        f"{LISTING}/7": _ruleset(),
        "graphql": _graph(0),
        PRODUCER: json.dumps({"check_runs": [{"app": {"id": 15368}}]}),
    }
    answers.update(changes or {})
    return answers


def _gh(answers: Answers) -> Callable[[Sequence[str]], str | None]:
    def gh(args: Sequence[str]) -> str | None:
        return answers.get(args[1])

    return gh


def _reason(capsys: pytest.CaptureFixture[str]) -> str:
    outcome = json.loads(capsys.readouterr().out)
    return str(outcome["data"]["decision"]["reason_code"])


def test_a_pinned_strict_unbypassable_ruleset_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(gh=_gh(_answers())) == 0
    assert _reason(capsys) == "ALL_RULES_PASS"


def test_a_check_required_by_name_only_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """Any status called "quality gate", from any token, would satisfy an unpinned check."""
    assert main(gh=_gh(_answers({f"{LISTING}/7": _ruleset(pinned=None)}))) == 2
    assert _reason(capsys) == "ERR_RULESET_CHECK_UNPINNED"


def test_a_ruleset_that_is_not_strict_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(gh=_gh(_answers({f"{LISTING}/7": _ruleset(strict=False)}))) == 2
    assert _reason(capsys) == "ERR_RULESET_NOT_STRICT"


def test_a_bypass_actor_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(gh=_gh(_answers({"graphql": _graph(1)}))) == 2
    assert _reason(capsys) == "ERR_RULESET_BYPASS_PRESENT"


def test_an_unreadable_bypass_count_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """A count that could not be read is not zero."""
    assert main(gh=_gh(_answers({"graphql": None}))) == 2
    assert _reason(capsys) == "ERR_RULESET_BYPASS_UNOBSERVED"


def test_a_gate_from_another_app_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """A pin that is not the producer would lock every merge out."""
    other = json.dumps({"check_runs": [{"app": {"id": 999}}]})
    assert main(gh=_gh(_answers({PRODUCER: other}))) == 2
    assert _reason(capsys) == "ERR_RULESET_PRODUCER_MISMATCH"


def test_an_unobservable_producer_is_not_a_refusal(capsys: pytest.CaptureFixture[str]) -> None:
    """CI's contents-only token cannot read check runs; that is recorded, not judged."""
    assert main(gh=_gh(_answers({PRODUCER: None}))) == 0
    assert _reason(capsys) == "ALL_RULES_PASS"


def test_a_missing_ruleset_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(gh=_gh(_answers({LISTING: json.dumps([])}))) == 2
    assert _reason(capsys) == "ERR_RULESET_MISSING"


def test_github_unreachable_halts(capsys: pytest.CaptureFixture[str]) -> None:
    """An unverifiable protection is not a verified one: halt, never pass."""
    assert main(gh=_gh(_answers({LISTING: None}))) == 1
    assert _reason(capsys) == "UNEVALUABLE"


def _changed(**fields: object) -> str:
    """recsys: the passing ruleset with top-level fields replaced."""
    ruleset = json.loads(_ruleset())
    ruleset.update(fields)
    return json.dumps(ruleset)


def _rules(kind: str, parameters: dict[str, object] | None) -> list[dict[str, object]]:
    """recsys: the passing rules with one rule's parameters replaced, or that rule removed."""
    rules: list[dict[str, object]] = json.loads(_ruleset())["rules"]
    kept = [rule for rule in rules if rule["type"] != kind]
    return kept if parameters is None else [*kept, {"type": kind, "parameters": parameters}]


def _refusal(capsys: pytest.CaptureFixture[str], ruleset: str) -> str:
    assert main(gh=_gh(_answers({f"{LISTING}/7": ruleset}))) == 2
    return _reason(capsys)


def test_an_unobserved_state_is_refused_by_the_policy() -> None:
    """recsys: evidence under another subject leaves the policy nothing to judge."""
    state = observe(_gh(_answers()))
    verdict = spine.evaluate(state, "not_ruleset_state", POLICY, ENTRYPOINT)
    codes = {rule.code for rule in verdict.rules if rule.outcome == "fail"}
    assert "ERR_RULESET_INPUT_MISSING" in codes, verdict


def test_a_ruleset_in_evaluate_mode_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """recsys: an evaluate-mode ruleset reports and permits, so nothing is enforced."""
    assert _refusal(capsys, _changed(enforcement="evaluate")) == "ERR_RULESET_NOT_ACTIVE"


def test_a_missing_protecting_rule_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """recsys: without the deletion rule, a protected branch can be deleted."""
    ruleset = _changed(rules=_rules("deletion", None))
    assert _refusal(capsys, ruleset) == "ERR_RULESET_RULE_MISSING"


def test_main_left_unprotected_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """recsys: a ruleset covering develop alone leaves the release branch open."""
    conditions = {"ref_name": {"include": ["refs/heads/develop"]}}
    assert _refusal(capsys, _changed(conditions=conditions)) == "ERR_RULESET_REF_UNPROTECTED"


def test_another_required_check_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """recsys: requiring some check is not requiring the quality gate."""
    parameters = {
        "strict_required_status_checks_policy": True,
        "required_status_checks": [{"context": "lint", "integration_id": 15368}],
    }
    ruleset = _changed(rules=_rules("required_status_checks", parameters))
    assert _refusal(capsys, ruleset) == "ERR_RULESET_CHECK_NOT_REQUIRED"


def test_a_squash_merge_method_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """recsys: squash collapses the history GitFlow's merge topology keeps."""
    parameters = {"allowed_merge_methods": ["merge", "squash"]}
    ruleset = _changed(rules=_rules("pull_request", parameters))
    assert _refusal(capsys, ruleset) == "ERR_RULESET_MERGE_METHODS"
