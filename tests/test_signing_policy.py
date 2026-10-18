"""Signing's policy refuses an absent or unlisted key by its own rules (A.89).

load_signer also refuses an unlisted key in Python, so a test of load_signer alone passes with the
policy's rule disabled: the guard is enforced twice and only one copy was proven. These proofs ask
runs.signing_keys for its codes directly, so each copy now has a test that fails without it.
"""

from __future__ import annotations

import spine
from signing import ENTRYPOINT, POLICY, SUBJECT, KeyState

PRIVATE = "/keys/ed25519.pem"


def _codes(state: KeyState) -> set[str]:
    found = spine.evaluate(state, SUBJECT, POLICY, ENTRYPOINT)
    return {rule.code for rule in found.rules if rule.outcome == "fail"}


def test_an_unlisted_key_is_refused_by_the_policy() -> None:
    state = KeyState(
        private_path=PRIVATE,
        private_exists=True,
        inside_repository=False,
        mode="0o600",
        keyid="probe",
        listed=False,
    )
    assert "ERR_SIGNING_KEY_UNLISTED" in _codes(state)


def test_an_absent_key_is_refused_by_the_policy() -> None:
    state = KeyState(
        private_path=PRIVATE,
        private_exists=False,
        inside_repository=False,
        mode=None,
        keyid=None,
        listed=False,
    )
    assert "ERR_SIGNING_KEY_ABSENT" in _codes(state)
