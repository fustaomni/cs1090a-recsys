# tests/test_plan_edit_refusals.py
"""Every plan:* verb refuses a bad spec as a closed outcome, never a traceback (A.128).

Given a [trace] holding maps_to, which plan:add fills itself, plan:add let pydantic's
ValidationError escape as a traceback: no command-outcome/v1 envelope, no code to branch on.
plan:retract already refused such a spec as spec_invalid; every verb now does, naming each
field, and a spec that cannot be read or parsed is refused as spec_unreadable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import plan_edit
from nonvacuous import nonempty

VERBS = ("add", "amend", "record", "retract")


def _refusal(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    envelope = json.loads(capsys.readouterr().out)
    assert isinstance(envelope, dict), envelope
    return envelope


def test_a_spec_with_an_undeclared_field_is_a_closed_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "spec.toml"
    spec.write_text("bogus = 1\n", encoding="utf-8")
    for verb in nonempty(VERBS):
        assert getattr(plan_edit, verb)([str(spec)], root=tmp_path) == 2, verb
        envelope = _refusal(capsys)
        assert envelope["code"] == "spec_invalid", envelope
        assert "bogus" in str(envelope["message"]), envelope


def test_a_spec_that_cannot_be_parsed_or_read_is_a_closed_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.toml"
    broken.write_text("= no key\n", encoding="utf-8")
    for spec in (broken, tmp_path / "absent.toml"):
        for verb in nonempty(VERBS):
            assert getattr(plan_edit, verb)([str(spec)], root=tmp_path) == 2, (verb, spec)
            assert _refusal(capsys)["code"] == "spec_unreadable", (verb, spec)
