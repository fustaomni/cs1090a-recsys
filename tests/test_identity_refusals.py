# tests/test_identity_refusals.py
"""A refused identity spec says which field broke which rule, in both tasks (A.130).

pydantic's ValidationError opens with its count, "1 validation error for IdentitySpec", and both
identity:set and template:identity kept only that first line, so generating cs1090a-volatility
refused a repository written as owner/name without naming the field or its pattern. pydantic
carries every error as e.errors(), each with its loc and msg; the refusal now names them all.

ONLY INVALID SPECS HERE: a valid one would make identity:set rewrite this repository's identity.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import project_identity
import template_identity
from template_identity import IdentityRequest

BAD = 'name = "probe-project"\nrepository = "example/probe-project"\n'
RULE = "String should match pattern"


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec.toml"
    spec.write_text(BAD, encoding="utf-8")
    return spec


def _message(capsys: pytest.CaptureFixture[str]) -> str:
    return str(json.loads(capsys.readouterr().out)["message"])


def test_a_spec_refusal_names_the_field_and_its_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert project_identity.main([str(_spec(tmp_path))]) == 2
    message = _message(capsys)
    assert "repository" in message and RULE in message, message


def test_template_identity_refuses_a_spec_with_the_same_detail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    fresh = IdentityRequest(
        destination=str(tmp_path), answers_present=True, commits=1, has_remote=False
    )
    monkeypatch.setattr(template_identity, "observe", lambda destination: fresh)
    assert template_identity.main([str(tmp_path), str(_spec(tmp_path))]) == 2
    message = _message(capsys)
    assert "repository" in message and RULE in message, message
