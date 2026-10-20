# tests/test_template_update_policy.py
"""runs.template.update judged on its own: each rule names its refusal, a valid request none.

Each rule is proven by varying one field of one complete, valid request, as A.127 proves
runs.worktree_skip's guards; test_template_update.py drives real Copier end to end (A.134).
"""

from __future__ import annotations

from nonvacuous import nonempty
from opa import denials

ENTRYPOINT = "data.runs.template.update.deny"
REQUEST: dict[str, object] = {
    "contract": "template-update/v1",
    "destination": "/srv/project",
    "answers_present": True,
    "source": "https://github.com/o/t.git",
    "template": "https://github.com/o/t.git",
    "recorded": "b" * 7,
    "ref": "a" * 40,
    "branch": "feature/update",
    "clean": True,
}


def _denied(**changed: object) -> str:
    return " ".join(denials(ENTRYPOINT, {"template_update": {**REQUEST, **changed}}))


def test_an_absent_request_is_refused_by_the_policy() -> None:
    assert "ERR_TEMPLATE_UPDATE_INPUT_MISSING" in " ".join(denials(ENTRYPOINT, {}))
    assert denials(ENTRYPOINT, {"template_update": REQUEST}) == []


def test_a_destination_that_was_not_generated_is_refused() -> None:
    assert "ERR_TEMPLATE_UPDATE_NOT_GENERATED" in _denied(answers_present=False)


def test_an_unpinned_ref_is_refused() -> None:
    assert "ERR_TEMPLATE_UPDATE_UNPINNED" in _denied(ref="main")


def test_a_project_from_another_template_is_refused() -> None:
    assert "ERR_TEMPLATE_UPDATE_FOREIGN" in _denied(source="https://github.com/o/other.git")


def test_a_dirty_project_is_refused() -> None:
    assert "ERR_TEMPLATE_UPDATE_DIRTY" in _denied(clean=False)


def test_a_protected_or_detached_branch_is_refused() -> None:
    for branch in nonempty(("main", "develop", "HEAD")):
        assert "ERR_TEMPLATE_UPDATE_PROTECTED" in _denied(branch=branch), branch


def test_a_project_already_at_the_ref_is_refused() -> None:
    assert "ERR_TEMPLATE_UPDATE_CURRENT" in _denied(recorded="a" * 7)
