# tests/test_sibling_fetch.py
"""A throttled sibling fetch is retried with curl's own backoff, within a bound (A.272)."""

from __future__ import annotations

import subprocess

import pytest

import sibling_pins

URL = "https://raw.githubusercontent.com/NixOS/nixpkgs/abc/pkgs/x/package.nix"


def _curl(monkeypatch: pytest.MonkeyPatch, code: int, stderr: str = "") -> list[list[str]]:
    """Every curl command fetch would run, answered with one exit code instead of run."""
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(command, code, 'version = "1.0";', stderr)

    # THE STDLIB MODULE ITSELF: sibling_pins only imports it, and imports are not re-exported.
    monkeypatch.setattr(subprocess, "run", run)
    return calls


def test_a_throttled_fetch_is_retried_with_backoff_and_a_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """curl retries 429 and 5xx with exponential backoff and Retry-After, bounded in total."""
    calls = _curl(monkeypatch, 0)
    assert sibling_pins.fetch(URL) == 'version = "1.0";'
    (command,) = calls
    assert int(command[command.index("--retry") + 1]) >= 3, command
    assert "--retry-max-time" in command, command
    assert "--retry-delay" not in command, "a fixed delay disables curl's backoff"


def test_a_fetch_that_keeps_failing_is_refused_by_its_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Past the bound, the failure is refused naming its URL and the retries spent."""
    _curl(monkeypatch, 22, "curl: (22) The requested URL returned error: 429")
    with pytest.raises(SystemExit, match=r"cannot fetch https://raw\S+ after \d+ retries"):
        sibling_pins.fetch(URL)
