"""sibling:origin realigns a sibling's origin to its declared source (A.219).

A clone whose origin was rewritten to another transport, here SSH on a machine that reaches
GitHub only over HTTPS, cannot fetch or push. sibling:origin reads the configured origin,
judges it on the spine against the declared source, and sets the declared source when only
the transport differs. An origin naming another repository is refused and left untouched.
"""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
DECLARED = "https://github.com/fustaomni/demo"


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: str) -> tuple[ModuleType, Path]:
    """A declared sibling whose clone is a fresh repository with only an origin."""
    subject = importlib.import_module("sibling_checkout")
    sibling = subject.Sibling(name="demo", source=DECLARED, tools={"uv": "0.12.22"})
    parent = tmp_path / "siblings"
    clone = parent / "demo"
    clone.mkdir(parents=True)
    _git(clone, "init", "--quiet", "-b", "develop")
    _git(clone, "remote", "add", "origin", origin)
    monkeypatch.setattr(subject, "declared", lambda root=None: (sibling,))
    monkeypatch.setattr(subject, "_siblings_parent", lambda: parent)
    return subject, clone


def _configured(clone: Path) -> str:
    return _git(clone, "config", "--get", "remote.origin.url")


def test_an_ssh_origin_of_the_declared_repository_is_realigned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same repository over SSH is set to the declared HTTPS source."""
    subject, clone = _clone(tmp_path, monkeypatch, "git@github.com:fustaomni/demo.git")
    assert subject.main(["--origin", "demo"]) == 0
    assert _configured(clone) == DECLARED
    outcome = json.loads(capsys.readouterr().out)
    assert outcome["code"] == "sibling_origin_aligned", outcome


def test_an_origin_already_declared_is_left_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An origin that already reads as the declared source is reported, not rewritten."""
    subject, clone = _clone(tmp_path, monkeypatch, DECLARED)
    assert subject.main(["--origin", "demo"]) == 0
    assert _configured(clone) == DECLARED
    outcome = json.loads(capsys.readouterr().out)
    assert outcome["code"] == "sibling_origin_unchanged", outcome


def test_an_origin_naming_another_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Only the transport may change: another repository's origin is refused, untouched."""
    foreign = "git@github.com:someone-else/demo.git"
    subject, clone = _clone(tmp_path, monkeypatch, foreign)
    assert subject.main(["--origin", "demo"]) != 0
    assert _configured(clone) == foreign
    outcome = json.loads(capsys.readouterr().out)
    # The command keeps its own refusal code; the rule that fired is named in the message.
    assert outcome["code"] == "sibling_origin_refused", outcome
    assert "ERR_SIBLING_ORIGIN_FOREIGN" in outcome["message"], outcome


def test_an_absent_origin_request_is_refused_by_the_policy() -> None:
    """With no sibling_origin input the policy refuses, never reading absence as allowed."""
    subject = importlib.import_module("sibling_checkout")
    evidence = subject.SiblingOrigin(
        name="demo",
        clone="/nowhere/demo",
        clone_exists=False,
        configured="no clone",
        declared=DECLARED,
        same_repository=False,
        already_declared=False,
    )
    found = subject.evaluate(
        evidence, "not_sibling_origin", subject.ORIGIN_POLICY, subject.ORIGIN_ENTRYPOINT
    )
    codes = {rule.code for rule in found.rules if rule.outcome == "fail"}
    assert "ERR_SIBLING_ORIGIN_INPUT_MISSING" in codes, found


def test_a_sibling_not_yet_cloned_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A declared sibling with no clone is refused by name before anything is touched."""
    subject = importlib.import_module("sibling_checkout")
    sibling = subject.Sibling(name="demo", source=DECLARED, tools={"uv": "0.12.22"})
    monkeypatch.setattr(subject, "declared", lambda root=None: (sibling,))
    monkeypatch.setattr(subject, "_siblings_parent", lambda: tmp_path / "siblings")
    assert subject.main(["--origin", "demo"]) != 0
    outcome = json.loads(capsys.readouterr().out)
    assert outcome["code"] == "sibling_origin_refused", outcome
    assert "ERR_SIBLING_ORIGIN_NO_CLONE" in outcome["message"], outcome
