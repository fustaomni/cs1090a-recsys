"""Each template policy's input guard, judged through the policy alone (A.121).

Every template task builds its request and asks its policy in the same call, so no ported
proof can reach an absent request, nor publish's unobserved remote. Each is proven here by
asking the policy directly, one proof per guard, so each safeguard names exactly one test.
"""

from __future__ import annotations

from opa import denials


def _refused(entrypoint: str, request: dict[str, object], code: str) -> None:
    assert code in " ".join(denials(entrypoint, request))


def test_an_absent_new_request_is_refused() -> None:
    _refused("data.runs.template.new.deny", {}, "ERR_TEMPLATE_INPUT_MISSING")


def test_an_absent_init_request_is_refused() -> None:
    _refused("data.runs.template.init.deny", {}, "ERR_INIT_INPUT_MISSING")


def test_an_absent_identity_request_is_refused() -> None:
    _refused("data.runs.template.identity.deny", {}, "ERR_IDENTITY_REQUEST_MISSING")


def test_an_absent_publish_request_is_refused() -> None:
    _refused("data.runs.template.publish.deny", {}, "ERR_PUBLISH_INPUT_MISSING")


def test_an_absent_discard_request_is_refused() -> None:
    _refused("data.runs.template.discard.deny", {}, "ERR_DISCARD_INPUT_MISSING")


def test_a_remote_that_could_not_be_observed_is_refused() -> None:
    # THE RULE'S MESSAGE NAMES THE REPOSITORY: without it the rule is undefined, not denied.
    publish = {"remote": "unknown", "repository": "example/project"}
    request: dict[str, object] = {"template_publish": publish}
    _refused("data.runs.template.publish.deny", request, "ERR_PUBLISH_REMOTE_UNKNOWN")
