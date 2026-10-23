# tests/test_repo_history_across.py
"""repo:history reads a clone upstream:checkout made, and nothing else outside (A.135).

cscie103 is private and its later commits are not at this repository's pin, so its history is
readable here only in the blobless clone upstream:checkout makes under .artifacts/upstream.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import repo_history


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _clone(base: Path) -> Path:
    """A repository where upstream:checkout would put one, with one traced commit."""
    clone = base / "upstream" / "other-0123456789ab"
    clone.mkdir(parents=True)
    _git(clone, "init", "-q", "-b", "develop")
    (clone / "f.txt").write_text("x\n", encoding="utf-8")
    _git(clone, "add", "f.txt")
    _git(clone, "commit", "-q", "-m", "feat: elsewhere\n\nPlan-Step: D.11")
    return clone


def test_a_clone_under_the_evidence_root_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clone = _clone(tmp_path)
    monkeypatch.setattr(repo_history, "EVIDENCE", tmp_path / "upstream")
    assert repo_history.main(["--repository", str(clone), "develop"]) == 0
    commits = json.loads(capsys.readouterr().out)["data"]["commits"]
    assert [commit["subject"] for commit in commits] == ["feat: elsewhere"], commits
    assert commits[0]["trailers"] == [{"key": "Plan-Step", "value": "D.11"}], commits
    assert commits[0]["files"] == ["f.txt"], commits


def test_a_repository_outside_the_evidence_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = _clone(tmp_path)
    monkeypatch.setattr(repo_history, "EVIDENCE", tmp_path / "elsewhere")
    with pytest.raises(SystemExit, match="reads only a clone under"):
        repo_history.main(["--repository", str(clone), "develop"])
