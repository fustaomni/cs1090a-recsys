"""A declared sibling with no FAS mode is cloned only to be measured (A.220).

The hub's survey reads every sibling it declares, and on a machine where no task runs in a
sibling, a FAS mode for it would be scope nobody uses. A sibling declared with no tools is
cloned, its origin judged on the spine, and nothing is written, trusted or set up. A sibling
with tools keeps its full path.
"""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
MEASURED = ("cs1090a-data-science", "cs1090a-spec-driven-development", "cscie103-olap-oltp")


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _source(tmp_path: Path) -> Path:
    """A sibling's canonical repository: develop, holding its mise.toml."""
    source = tmp_path / "origin"
    source.mkdir()
    _git(source, "init", "--quiet", "-b", "develop")
    (source / "mise.toml").write_text("[tasks.hello]\nrun = 'true'\n", encoding="utf-8")
    _git(source, "add", "mise.toml")
    _git(source, "commit", "--quiet", "-m", "config")
    return source


def _declare(
    monkeypatch: pytest.MonkeyPatch, subject: ModuleType, sibling: object, parent: Path
) -> None:
    monkeypatch.setattr(subject, "declared", lambda root=None: (sibling,))
    monkeypatch.setattr(subject, "_siblings_parent", lambda: parent)


def test_a_sibling_without_tools_is_cloned_without_a_fas_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cloned and judged, and no override is written, trusted or set up."""
    subject = importlib.import_module("sibling_checkout")
    sibling = subject.Sibling(name="demo", source=str(_source(tmp_path)), tools={})
    parent = tmp_path / "siblings"
    _declare(monkeypatch, subject, sibling, parent)
    try:
        exit_code = subject.main(["demo"])
    except SystemExit as stopped:
        pytest.fail(f"a measured sibling went past its clone: {stopped}")
    assert exit_code == 0
    clone = parent / "demo"
    assert (clone / "mise.toml").is_file()
    assert not (clone / subject.OVERRIDE).exists(), "a FAS mode was written"
    outcome = json.loads(capsys.readouterr().out)
    assert outcome["code"] == "sibling_cloned", outcome


def test_a_sibling_with_tools_still_gets_its_fas_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sibling that declares tools goes on to have its FAS mode written."""
    subject = importlib.import_module("sibling_checkout")
    sibling = subject.Sibling(name="demo", source=str(_source(tmp_path)), tools={"uv": "0.12.22"})
    _declare(monkeypatch, subject, sibling, tmp_path / "siblings")

    def written(clone: Path, declared: object) -> Path:
        raise SystemExit("fas mode written")

    monkeypatch.setattr(subject, "write_override", written)
    with pytest.raises(SystemExit, match="fas mode written"):
        subject.main(["demo"])


def test_the_hubs_measured_siblings_are_declared_without_tools() -> None:
    """The three the hub's survey reads are declared, sourced over HTTPS, with no FAS mode."""
    subject = importlib.import_module("sibling_checkout")
    declared = {sibling.name: sibling for sibling in subject.declared()}
    for name in MEASURED:
        assert name in declared, sorted(declared)
        assert declared[name].tools == {}, declared[name]
        assert declared[name].source.startswith("https://github.com/"), declared[name]
