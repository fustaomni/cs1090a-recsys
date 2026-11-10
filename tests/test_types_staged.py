# tests/test_types_staged.py
"""A commit's staged Python is type-checked before the commit is made (A.267)."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

import types_staged
from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent


def _record(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Every command types_staged would run, recorded instead of run."""
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    # THE STDLIB MODULE ITSELF: types_staged only imports it, and imports are not re-exported.
    monkeypatch.setattr(subprocess, "run", run)
    return calls


def test_pre_commit_type_checks_the_staged_python_files(monkeypatch: pytest.MonkeyPatch) -> None:
    hooks: dict[str, Any] = yaml.safe_load((ROOT / "lefthook.yml").read_text(encoding="utf-8"))
    jobs = hooks["pre-commit"]["jobs"]
    staged = [job for job in jobs if job.get("run") == "mise run types:staged {staged_files}"]
    assert staged and staged[0].get("glob") == "*.py", jobs
    calls = _record(monkeypatch)
    assert types_staged.main(["scripts/a.py", "tests/test_b.py"]) == 0
    platforms = [call[call.index("--platform") + 1] for call in calls]
    assert platforms == ["darwin", "linux"], calls
    assert all(call[-2:] == ["scripts/a.py", "tests/test_b.py"] for call in nonempty(calls)), calls


def test_the_staged_check_is_incremental_and_skips_a_commit_without_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record(monkeypatch)
    assert types_staged.main(["README.md", "site/src/bind.js"]) == 0
    assert calls == [], "a commit without Python ran mypy"
    assert types_staged.main(["scripts/a.py"]) == 0
    assert all("--incremental" in call for call in nonempty(calls)), calls


def test_mypy_searches_where_pytest_imports() -> None:
    """mypy resolves scripts/ modules from the path pytest imports them from (A.274)."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pythonpath = config["tool"]["pytest"]["ini_options"]["pythonpath"]
    assert config["tool"]["mypy"].get("mypy_path") == pythonpath, config["tool"]["mypy"]


def test_a_test_staged_alone_resolves_its_scripts_imports() -> None:
    """A test staged without the scripts it imports still type-checks, as in a real commit."""
    assert types_staged.main(["tests/test_types_staged.py"]) == 0


def test_each_platform_keeps_its_own_mypy_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """A platform never shares a cache with the other, whose entries mypy would discard (A.275)."""
    calls = _record(monkeypatch)
    assert types_staged.main(["scripts/a.py"]) == 0
    caches = {
        call[call.index("--platform") + 1]: call[call.index("--cache-dir") + 1]
        for call in nonempty(calls)
    }
    assert caches == {"darwin": ".mypy_cache/darwin", "linux": ".mypy_cache/linux"}, calls


def test_the_full_gate_shares_the_staged_checks_caches() -> None:
    """The full gate writes the caches the staged check reads, so a commit after it starts warm."""
    run = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))["tasks"]["types"]["run"]
    for platform in nonempty(types_staged.PLATFORMS):
        assert f"mypy --platform {platform} --cache-dir .mypy_cache/{platform}" in run, run
