"""A declared sibling is cloned, given a FAS mode, and trusted only as merged (A.185).

cscie103-data-engineering runs every task inside nix develop, which FAS OnDemand cannot run, so
the reference repository was workable only on the laptop. sibling:checkout clones a declared
sibling from its canonical source, writes a mise.local.toml that replaces the Nix shell with bash
and pins the same tools, keeps it out of the tree through .git/info/exclude, and trusts the
sibling's own mise.toml only unmodified at a commit on its develop: provenance, not content,
since this repository's founding policy describes this repository alone.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

import spine

ROOT = Path(__file__).resolve().parent.parent
TOOLS = {"uv": "0.12.23", "opa": "1.21.1"}


def _subject() -> ModuleType:
    found = importlib.util.find_spec("sibling_checkout")
    assert found is not None, "sibling:checkout does not exist yet"
    return importlib.import_module("sibling_checkout")


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _origin(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / "remote" / name
    repo.mkdir(parents=True)
    _git(repo, "init", "--quiet", "--initial-branch=develop")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "mise.toml").write_text('[task_config]\nshell = "nix develop --command bash -c"\n')
    _git(repo, "add", "mise.toml")
    _git(repo, "commit", "--quiet", "-m", "first")
    return repo


def _sibling(subject: ModuleType, source: Path) -> object:
    return subject.Sibling(name="demo", source=str(source), tools=TOOLS)


def test_a_declared_sibling_is_cloned_from_its_canonical_source(tmp_path: Path) -> None:
    subject = _subject()
    source = _origin(tmp_path, "demo")
    clone = subject.checkout(_sibling(subject, source), tmp_path / "siblings")
    assert clone == tmp_path / "siblings" / "demo", clone
    assert _git(clone, "remote", "get-url", "origin") == str(source)


def test_an_existing_clone_from_another_source_is_refused(tmp_path: Path) -> None:
    subject = _subject()
    source = _origin(tmp_path, "demo")
    other = _origin(tmp_path / "elsewhere", "demo")
    subprocess.run(
        ["git", "clone", "--quiet", str(other), str(tmp_path / "siblings" / "demo")],
        capture_output=True,
        text=True,
        check=True,
    )
    with pytest.raises(SystemExit) as refused:
        subject.checkout(_sibling(subject, source), tmp_path / "siblings")
    assert str(other) in str(refused.value), refused.value


def test_the_override_replaces_the_nix_shell_and_pins_the_declared_tools(tmp_path: Path) -> None:
    subject = _subject()
    parsed = tomllib.loads(subject.override_text(_sibling(subject, tmp_path)))
    assert parsed["task_config"] == {"shell": "bash -c"}, parsed
    assert parsed["tools"] == TOOLS, parsed


def test_the_override_leaves_the_clone_clean(tmp_path: Path) -> None:
    subject = _subject()
    source = _origin(tmp_path, "demo")
    sibling = _sibling(subject, source)
    clone = subject.checkout(sibling, tmp_path / "siblings")
    subject.write_override(clone, sibling)
    assert (clone / "mise.local.toml").read_text() == subject.override_text(sibling)
    assert _git(clone, "status", "--porcelain") == "", "the override shows in the tree"


def _refused_only_when_broken(field: str, code: str) -> None:
    """Sound evidence is trusted; the same evidence with one field false is refused by code."""
    subject = _subject()
    sound = {"name": "demo", "head_on_develop": True, "config_unmodified": True}
    evidence = subject.SiblingTrust(**{**sound, "override_matches": True})
    found = spine.evaluate(evidence, "sibling_trust", subject.POLICY, subject.ENTRYPOINT)
    assert not [rule.code for rule in found.rules if rule.outcome == "fail"], found
    broken = subject.SiblingTrust(**{**sound, "override_matches": True, field: False})
    found = spine.evaluate(broken, "sibling_trust", subject.POLICY, subject.ENTRYPOINT)
    assert code in [rule.code for rule in found.rules if rule.outcome == "fail"], found


def test_a_sibling_head_off_its_develop_is_not_trusted() -> None:
    _refused_only_when_broken("head_on_develop", "ERR_SIBLING_HEAD_NOT_ON_DEVELOP")


def test_a_modified_sibling_config_is_not_trusted() -> None:
    _refused_only_when_broken("config_unmodified", "ERR_SIBLING_CONFIG_MODIFIED")


def test_a_mismatched_override_is_not_trusted() -> None:
    _refused_only_when_broken("override_matches", "ERR_SIBLING_OVERRIDE_MISMATCH")


def test_an_absent_trust_request_is_refused_by_the_policy() -> None:
    subject = _subject()
    sound = {"head_on_develop": True, "config_unmodified": True, "override_matches": True}
    evidence = subject.SiblingTrust(name="demo", **sound)
    found = spine.evaluate(evidence, "not_sibling_trust", subject.POLICY, subject.ENTRYPOINT)
    codes = [rule.code for rule in found.rules if rule.outcome == "fail"]
    assert "ERR_SIBLING_TRUST_INPUT_MISSING" in codes, found


def test_every_declared_tool_is_a_name_in_the_mise_registry() -> None:
    """A.186: mise resolves a tool by its registry shorthand; any other name is not installed."""
    subject = _subject()
    listed = subprocess.run(["mise", "registry"], capture_output=True, text=True, check=True)
    names = {line.split()[0] for line in listed.stdout.splitlines() if line.strip()}
    assert names, "mise listed no registry"
    declared = {tool for sibling in subject.declared(ROOT) for tool in sibling.tools}
    assert declared, "no sibling declares a tool"
    assert declared <= names, sorted(declared - names)


def test_a_trusted_sibling_is_set_up_by_its_own_setup_task(tmp_path: Path) -> None:
    """A.186: as worktree:add does, the sibling's own setup runs, the caller's VIRTUAL_ENV gone."""
    subject = _subject()
    assert hasattr(subject, "set_up"), "sibling:checkout does not set a sibling up"
    seen: list[tuple[list[str], Path, dict[str, str]]] = []

    def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> int:
        seen.append((command, cwd, env))
        return 0

    caller = {"VIRTUAL_ENV": "/elsewhere/.venv", "PATH": "/usr/bin"}
    subject.set_up(tmp_path, run=run, environ=caller)
    assert [(command, cwd) for command, cwd, _ in seen] == [(["mise", "run", "setup"], tmp_path)]
    assert "VIRTUAL_ENV" not in seen[0][2], seen


def test_a_failed_setup_is_refused_by_name(tmp_path: Path) -> None:
    """A.186: a sibling whose setup fails is not workable, and says so."""
    subject = _subject()
    assert hasattr(subject, "set_up"), "sibling:checkout does not set a sibling up"

    def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> int:
        return 1

    with pytest.raises(SystemExit) as refused:
        subject.set_up(tmp_path, run=run, environ={"PATH": "/usr/bin"})
    assert "setup" in str(refused.value), refused.value


def test_cscie103_is_declared_at_its_canonical_source_with_its_toolchain() -> None:
    subject = _subject()
    declared = {sibling.name: sibling for sibling in subject.declared(ROOT)}
    cscie103 = declared["cscie103-data-engineering"]
    assert cscie103.source == "https://github.com/fustaomni/cscie103-data-engineering"
    expected = {
        "betterleaks",
        "databricks-cli",
        "java",
        "lefthook",
        "opa",
        "osv-scanner",
        "regal",
        "uv",
        "zizmor",
    }
    assert set(cscie103.tools) == expected, cscie103.tools
