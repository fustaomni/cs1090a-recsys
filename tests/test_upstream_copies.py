"""Untracked copies of an upstream are verified against its pinned tree, never assumed (A.114).

A copy matching the blob at the same path in the upstream's tree at its pinned commit is
recoverable from that commit, so removing it loses nothing. Any other copy is kept and named: a
changed file, or one the upstream never had, may be work no commit holds.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import spine
import upstream_copies
from gitenv import scrubbed_env
from nonvacuous import nonempty


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, env=scrubbed_env(), capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _repository(path: Path, files: dict[str, str]) -> str:
    path.mkdir(parents=True)
    _git(path, "init", "--quiet")
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "Test")
    for name, text in files.items():
        (path / name).write_text(text, encoding="utf-8")
    _git(path, "add", "--all")
    _git(path, "commit", "--quiet", "--message", "initial")
    return _git(path, "rev-parse", "HEAD")


def _scene(tmp_path: Path) -> tuple[Path, str, str]:
    """An upstream holding a.txt and b.txt; a checkout holding three untracked copies."""
    source = tmp_path / "upstream"
    commit = _repository(source, {"a.txt": "alpha", "b.txt": "beta"})
    local = tmp_path / "local"
    _repository(local, {"README.md": "local"})
    (local / "a.txt").write_text("alpha", encoding="utf-8")
    (local / "b.txt").write_text("changed", encoding="utf-8")
    (local / "c.txt").write_text("new", encoding="utf-8")
    return local, str(source), commit


def _evidence(tmp_path: Path) -> Path:
    return tmp_path / "evidence"


def test_only_the_copy_matching_the_pin_is_verified(tmp_path: Path) -> None:
    local, source, commit = _scene(tmp_path)
    inventory = upstream_copies.observe(local, source, commit, _evidence(tmp_path))
    found = upstream_copies.judge(inventory)
    unverified = "ERR_COPIES_UNVERIFIED"
    kept = [f for rule in found.rules if rule.code == unverified for f in rule.findings]
    assert len(kept) == 2, kept
    assert any("b.txt" in line for line in kept), kept
    assert any("c.txt" in line for line in kept), kept
    assert not any("a.txt" in line for line in nonempty(kept)), kept


def test_a_dry_run_removes_nothing(tmp_path: Path) -> None:
    local, source, commit = _scene(tmp_path)
    upstream_copies.main([str(local), source, commit], root=_evidence(tmp_path))
    assert (local / "a.txt").exists()
    assert (local / "b.txt").exists()
    assert (local / "c.txt").exists()


def test_no_unverified_upstream_copy_remains(tmp_path: Path) -> None:
    """With --yes the verified copy is removed, and every other copy is kept and named."""
    local, source, commit = _scene(tmp_path)
    code = upstream_copies.main([str(local), source, commit, "--yes"], root=_evidence(tmp_path))
    assert code == 1
    assert not (local / "a.txt").exists()
    assert (local / "b.txt").read_text(encoding="utf-8") == "changed"
    assert (local / "c.txt").read_text(encoding="utf-8") == "new"
    left = upstream_copies.observe(local, source, commit, _evidence(tmp_path)).copies
    assert sorted(copy.path for copy in left) == ["b.txt", "c.txt"]


def test_an_absent_inventory_is_refused_by_the_policy() -> None:
    inventory = upstream_copies.CopyInventory(checkout="x", source="y", commit="0" * 40, copies=())
    policy, entrypoint = upstream_copies.POLICY, upstream_copies.ENTRYPOINT
    found = spine.evaluate(inventory, "not_upstream_copies", policy, entrypoint)
    failing = {rule.code for rule in found.rules if rule.outcome == "fail"}
    assert "ERR_COPIES_INPUT_MISSING" in failing
