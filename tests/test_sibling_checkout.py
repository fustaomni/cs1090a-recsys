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
import inspect
import json
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


def _two_branches(tmp_path: Path) -> Path:
    """A.187: an origin whose default branch is main, with develop one commit ahead of it."""
    repo = tmp_path / "remote" / "demo"
    repo.mkdir(parents=True)
    _git(repo, "init", "--quiet", "--initial-branch=main")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "mise.toml").write_text('[task_config]\nshell = "nix develop --command bash -c"\n')
    _git(repo, "add", "mise.toml")
    _git(repo, "commit", "--quiet", "-m", "released")
    _git(repo, "switch", "--quiet", "-c", "develop")
    _ahead(repo, "integrated")
    _git(repo, "switch", "--quiet", "main")
    return repo


def _ahead(repo: Path, message: str) -> None:
    """One more commit on the origin's develop, which is left checked out as it was."""
    current = _git(repo, "symbolic-ref", "--short", "HEAD")
    _git(repo, "switch", "--quiet", "develop")
    (repo / f"{message}.txt").write_text(f"{message}\n")
    _git(repo, "add", f"{message}.txt")
    _git(repo, "commit", "--quiet", "-m", message)
    _git(repo, "switch", "--quiet", current)


def _plain_clone(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--quiet", str(source), str(target)], check=True)
    return target


def test_a_sibling_is_cloned_on_its_declared_branch(tmp_path: Path) -> None:
    """A.187: the default branch is main; the sibling is still checked out on develop."""
    subject = _subject()
    source = _two_branches(tmp_path)
    clone = subject.checkout(_sibling(subject, source), tmp_path / "siblings")
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == "develop"
    assert _git(clone, "rev-parse", "HEAD") == _git(source, "rev-parse", "develop")


def test_an_existing_clone_on_another_branch_is_moved_to_its_own(tmp_path: Path) -> None:
    """A.187: a clean clone on main is switched to develop, its declared branch."""
    subject = _subject()
    source = _two_branches(tmp_path)
    _plain_clone(source, tmp_path / "siblings" / "demo")
    clone = subject.checkout(_sibling(subject, source), tmp_path / "siblings")
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == "develop"


def test_a_stale_clone_is_fast_forwarded_to_its_branch_tip(tmp_path: Path) -> None:
    """A.187: a clone behind its branch is brought to the remote tip, by fast-forward only."""
    subject = _subject()
    source = _two_branches(tmp_path)
    sibling = _sibling(subject, source)
    clone = subject.checkout(sibling, tmp_path / "siblings")
    _ahead(source, "later")
    subject.checkout(sibling, tmp_path / "siblings")
    assert _git(clone, "rev-parse", "HEAD") == _git(source, "rev-parse", "develop")


def test_a_dirty_clone_off_its_branch_is_refused(tmp_path: Path) -> None:
    """A.187: a clone with uncommitted tracked changes is never switched or merged into."""
    subject = _subject()
    source = _two_branches(tmp_path)
    clone = _plain_clone(source, tmp_path / "siblings" / "demo")
    (clone / "mise.toml").write_text("# changed by hand\n")
    with pytest.raises(SystemExit) as refused:
        subject.checkout(_sibling(subject, source), tmp_path / "siblings")
    assert "uncommitted" in str(refused.value), refused.value


def test_a_clone_behind_its_branch_tip_is_not_trusted(tmp_path: Path) -> None:
    """A.187: an ancestor of develop is not develop; trust needs HEAD to be its branch's tip."""
    subject = _subject()
    source = _two_branches(tmp_path)
    sibling = _sibling(subject, source)
    clone = subject.checkout(sibling, tmp_path / "siblings")
    _ahead(source, "later")
    assert subject.observe(clone, sibling).head_on_develop is False


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
    sound = {
        "name": "demo",
        "head_on_develop": True,
        "config_unmodified": True,
        "toolchain_current": True,
    }
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
    sound = {
        "head_on_develop": True,
        "config_unmodified": True,
        "override_matches": True,
        "toolchain_current": True,
    }
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


def test_a_sibling_whose_lock_moved_is_observed_stale(tmp_path: Path) -> None:
    """A.188: the clone's flake.lock names another nixpkgs than the pins were read at."""
    subject = _subject()
    assert "toolchain_current" in subject.SiblingTrust.model_fields, "the lock is not observed"
    source = _origin(tmp_path, "demo")
    lock = {"nodes": {"nixpkgs": {"locked": {"rev": "b" * 40}}}}
    (source / "flake.lock").write_text(json.dumps(lock))
    _git(source, "add", "flake.lock")
    _git(source, "commit", "--quiet", "-m", "lock")
    stale = subject.Sibling(name="demo", source=str(source), tools=TOOLS, nixpkgs="a" * 40)
    clone = subject.checkout(stale, tmp_path / "siblings")
    assert subject.observe(clone, stale).toolchain_current is False
    current = subject.Sibling(name="demo", source=str(source), tools=TOOLS, nixpkgs="b" * 40)
    assert subject.observe(clone, current).toolchain_current is True


def test_a_stale_toolchain_is_not_trusted() -> None:
    """A.188: a sibling whose lock moved past the recorded nixpkgs is refused, by its code."""
    subject = _subject()
    assert "toolchain_current" in subject.SiblingTrust.model_fields, "the lock is not observed"
    _refused_only_when_broken("toolchain_current", "ERR_SIBLING_TOOLCHAIN_STALE")


def test_the_stale_toolchain_refusal_names_sibling_pin() -> None:
    """A.203: the refusal says how to regenerate the pins, so nobody retypes them."""
    subject = _subject()
    evidence = subject.SiblingTrust(
        name="demo",
        head_on_develop=True,
        config_unmodified=True,
        override_matches=True,
        toolchain_current=False,
    )
    found = spine.evaluate(evidence, "sibling_trust", subject.POLICY, subject.ENTRYPOINT)
    text = spine.reasons(found)
    assert "sibling:pin demo" in text, text


def test_the_override_is_rewritten_on_a_clone_mid_feature(tmp_path: Path) -> None:
    """A.189: the declared FAS mode lands; the branch and the uncommitted work stay as they are."""
    subject = _subject()
    assert hasattr(subject, "refresh_override"), "no override can be written without a checkout"
    source = _origin(tmp_path, "demo")
    clone = subject.checkout(_sibling(subject, source), tmp_path / "siblings")
    _git(clone, "switch", "--quiet", "-c", "feature/wip")
    (clone / "mise.toml").write_text("# work in progress\\n")
    (clone / "mise.local.toml").write_text("# an older FAS mode\\n")
    repinned = subject.Sibling(name="demo", source=str(source), tools={"uv": "0.12.22"})
    subject.refresh_override(repinned, tmp_path / "siblings", trust=lambda _: 0)
    assert (clone / "mise.local.toml").read_text() == subject.override_text(repinned)
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == "feature/wip"
    assert (clone / "mise.toml").read_text() == "# work in progress\\n"


def test_an_override_is_never_written_into_another_sources_clone(tmp_path: Path) -> None:
    """A.189: a directory cloned from elsewhere is refused, and nothing is written into it."""
    subject = _subject()
    assert hasattr(subject, "refresh_override"), "no override can be written without a checkout"
    source = _origin(tmp_path, "demo")
    other = _origin(tmp_path / "elsewhere", "demo")
    _plain_clone(other, tmp_path / "siblings" / "demo")
    with pytest.raises(SystemExit) as refused:
        subject.refresh_override(_sibling(subject, source), tmp_path / "siblings")
    assert str(other) in str(refused.value), refused.value
    assert not (tmp_path / "siblings" / "demo" / "mise.local.toml").exists()


def test_an_override_needs_an_existing_clone(tmp_path: Path) -> None:
    """A.189: with no clone there is nothing to write into; sibling:checkout makes one."""
    subject = _subject()
    assert hasattr(subject, "refresh_override"), "no override can be written without a checkout"
    with pytest.raises(SystemExit) as refused:
        subject.refresh_override(_sibling(subject, tmp_path), tmp_path / "siblings")
    assert "sibling:checkout" in str(refused.value), refused.value


def test_an_absent_override_request_is_refused_by_the_policy() -> None:
    """A.189: with no observation supplied, the override is refused, never read as allowed."""
    subject = _subject()
    assert hasattr(subject, "OVERRIDE_POLICY"), "no policy judges an override"
    evidence = subject.SiblingOverride(
        name="demo", clone="/c", clone_exists=True, origin="/o", origin_matches=True
    )
    found = spine.evaluate(
        evidence, "not_sibling_override", subject.OVERRIDE_POLICY, subject.OVERRIDE_ENTRYPOINT
    )
    codes = [rule.code for rule in found.rules if rule.outcome == "fail"]
    assert "ERR_SIBLING_OVERRIDE_INPUT_MISSING" in codes, found


def test_a_rewritten_override_is_trusted_again(tmp_path: Path) -> None:
    """A.190: mise trusts by content, so the rewritten file is trusted again, by its path."""
    subject = _subject()
    parameters = inspect.signature(subject.refresh_override).parameters
    assert "trust" in parameters, "a rewritten override is left untrusted"
    source = _origin(tmp_path, "demo")
    parent = tmp_path / "siblings"
    clone = subject.checkout(_sibling(subject, source), parent)
    trusted: list[Path] = []

    def trust(path: Path) -> int:
        trusted.append(path)
        return 0

    subject.refresh_override(_sibling(subject, source), parent, trust=trust)
    assert trusted == [clone / "mise.local.toml"], trusted


def test_an_override_mise_will_not_trust_is_refused(tmp_path: Path) -> None:
    """A.190: written but untrusted is not done, since mise would refuse every task there."""
    subject = _subject()
    parameters = inspect.signature(subject.refresh_override).parameters
    assert "trust" in parameters, "a rewritten override is left untrusted"
    source = _origin(tmp_path, "demo")
    parent = tmp_path / "siblings"
    subject.checkout(_sibling(subject, source), parent)
    with pytest.raises(SystemExit) as refused:
        subject.refresh_override(_sibling(subject, source), parent, trust=lambda _: 1)
    assert "trust" in str(refused.value), refused.value


def test_cscie103_declares_where_its_toolchain_comes_from() -> None:
    """A.188: the nixpkgs revision its flake.lock pins, and each tool's nixpkgs file."""
    subject = _subject()
    cscie103 = {s.name: s for s in subject.declared(ROOT)}["cscie103-data-engineering"]
    assert getattr(cscie103, "nixpkgs", None), "no nixpkgs revision is recorded"
    assert set(getattr(cscie103, "packages", {})) == set(cscie103.tools), cscie103


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
