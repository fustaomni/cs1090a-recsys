"""deps.add's and machine.testing's rules each refuse their own case, by code (A.89).

deps:add's tests judge the task's outcome, refused and rolled back, never which rule refused, and
machine.testing is exercised only by conftest's session check. These proofs ask each policy for
its codes, with every field its rules and messages read, since a message reading a missing field
leaves its rule silent.
"""

from __future__ import annotations

from collections.abc import Mapping

from opa import denials

DEPS = "data.deps.add.deny"
GIT_ENV = "data.machine.testing.deny"


def _codes(entrypoint: str, payload: Mapping[str, object]) -> set[str]:
    return {denial.split("]", 1)[0].removeprefix("[") for denial in denials(entrypoint, payload)}


def _change(**fields: object) -> dict[str, object]:
    change: dict[str, object] = {
        "package": "probe",
        "lock_current": True,
        "landed": True,
        "changed": [],
        "removed": [],
    }
    change.update(fields)
    return {"deps_change": change}


def test_a_stale_lock_is_refused_by_the_policy() -> None:
    assert "ERR_DEPS_LOCK_STALE" in _codes(DEPS, _change(lock_current=False))


def test_a_package_that_did_not_land_is_refused_by_the_policy() -> None:
    assert "ERR_DEPS_NOT_ADDED" in _codes(DEPS, _change(landed=False))


def test_a_changed_package_is_refused_by_the_policy() -> None:
    assert "ERR_DEPS_EXISTING_CHANGED" in _codes(DEPS, _change(changed=["other"]))


def test_a_removed_package_is_refused_by_the_policy() -> None:
    assert "ERR_DEPS_REMOVED" in _codes(DEPS, _change(removed=["other"]))


def test_an_unobserved_git_environment_is_refused_by_the_policy() -> None:
    payload: dict[str, object] = {"git_isolation": {"local_variables": [], "present": []}}
    assert "ERR_TEST_GIT_ENV_UNOBSERVED" in _codes(GIT_ENV, payload)


def test_a_leaked_git_variable_is_refused_by_the_policy() -> None:
    payload = {"git_isolation": {"local_variables": ["GIT_DIR"], "present": ["GIT_DIR"]}}
    assert "ERR_TEST_GIT_ENV_LEAKED" in _codes(GIT_ENV, payload)
