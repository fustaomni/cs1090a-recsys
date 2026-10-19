"""The founding gate and the re-trust of a checkout are one operation (A.27)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import machine_trust
from machine_trust import TrustDecision, trust

TEXT = '[tasks.probe]\nrun = "true"\n'


class _Recorder:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(
        self, command: list[str], cwd: Path, stdin: str | None
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")


def test_the_trust_task_gates_before_it_trusts(tmp_path: Path) -> None:
    events = tmp_path / "events.tsv"
    denied = _Recorder()
    refused = trust(tmp_path, TEXT, allows=lambda _: False, run=denied, events=events)
    assert (refused.allowed, refused.trusted, denied.commands) == (False, False, [])
    assert not events.exists()
    allowed = _Recorder()
    done = trust(tmp_path, TEXT, allows=lambda _: True, run=allowed, events=events)
    assert (done.allowed, done.trusted) == (True, True)
    assert allowed.commands == [["mise", "trust", str((tmp_path / "mise.toml").resolve())]]
    assert done.sha256 in events.read_text(encoding="utf-8")


def test_a_linked_worktree_is_not_trusted_by_inheritance_under_paranoid(tmp_path: Path) -> None:
    main, linked = tmp_path / "main", tmp_path / "linked"
    recorder = _Recorder()
    trust(linked, TEXT, allows=lambda _: True, run=recorder, events=tmp_path / "events.tsv")
    assert recorder.commands == [["mise", "trust", str((linked / "mise.toml").resolve())]]
    assert str(main) not in recorder.commands[0][2]


def test_a_named_checkout_is_trusted_by_its_own_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """machine:trust <checkout> gates that checkout's own mise.toml, never this one's (A.122)."""
    (tmp_path / "mise.toml").write_text(TEXT, encoding="utf-8")
    seen: list[tuple[Path, str]] = []

    def recorded(checkout: Path, text: str) -> TrustDecision:
        seen.append((checkout, text))
        config = str(checkout / "mise.toml")
        return TrustDecision(config=config, sha256="0", allowed=True, trusted=True)

    monkeypatch.setattr(machine_trust, "trust", recorded)
    assert machine_trust.main([str(tmp_path)]) == 0
    assert seen == [(tmp_path.resolve(), TEXT)], seen
