# tests/test_tool_provenance.py
"""Every pinned tool's artifact carries verified provenance (plan A.9).

mise.lock records the provenance mise verified at install: slsa, cosign, minisign or
github-attestations. opa and regal publish none of those, but their releases are immutable and
GitHub attests every asset, which `gh release verify-asset` checks. contracts/tool-provenance.toml
records that verification: the asset, its digest and the command. Every locked tool must have one
or the other, and a record must match the lock exactly, so a re-lock to other bytes fails here
until it is verified again.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from tools_verify import aube_integrity

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = "platforms.linux-x64"
MISE_KINDS = frozenset({"slsa", "cosign", "minisign", "github-attestations"})


def _load(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _npm_unverified(name: str, entry: dict[str, object], found: object) -> list[str]:
    """An npm-backend tool is verified only by its record of npm audit signatures (A.279)."""
    if not isinstance(found, dict) or found.get("kind") != "npm-registry-provenance":
        return [f"{name}: an npm-backend tool with no recorded registry provenance"]
    aube = entry.get("aube")
    assert isinstance(aube, dict), entry
    lock_dir = ROOT / str(aube["path"])
    integrity = aube_integrity(lock_dir, name.removeprefix("npm:"), str(entry["version"]))
    if (found.get("version"), found.get("integrity")) != (entry["version"], integrity):
        return [f"{name}: the recorded verification is not of the locked package"]
    return []


def _unverified(lock: dict[str, object], record: dict[str, object]) -> list[str]:
    tools = lock["tools"]
    assert isinstance(tools, dict), tools
    recorded = record.get("tools", [])
    assert isinstance(recorded, list), recorded
    by_name = {str(r["name"]): r for r in recorded if isinstance(r, dict)}
    problems = []
    for name, entries in tools.items():
        entry = entries[0]
        if PLATFORM not in entry:
            problems.extend(_npm_unverified(name, entry, by_name.get(name)))
            continue
        platform = entry[PLATFORM]
        if platform.get("provenance") in MISE_KINDS:
            continue
        found = by_name.get(name)
        if found is None:
            problems.append(f"{name}: no provenance in mise.lock and no recorded verification")
            continue
        asset = str(platform["url"]).rsplit("/", 1)[-1]
        if (found.get("version"), found.get("asset"), "sha256:" + str(found.get("sha256"))) != (
            entry["version"],
            asset,
            platform["checksum"],
        ):
            problems.append(f"{name}: the recorded verification is not of the locked artifact")
    return sorted(problems)


def test_every_locked_tool_names_its_provenance() -> None:
    lock = _load(ROOT / "mise.lock")
    record = _load(ROOT / "contracts" / "tool-provenance.toml")
    assert record.get("contract") == "tool-provenance/v1", record.get("contract")
    problems = _unverified(lock, record)
    assert not problems, "unverified: " + "; ".join(problems)


def test_an_unverified_tool_is_named() -> None:
    """The paired negative control: a tool with neither, and a stale record, are each named."""
    url = "https://example.invalid/v1/tool_linux"
    lock: dict[str, object] = {
        "tools": {
            "bare": [{"version": "1", PLATFORM: {"url": url, "checksum": "sha256:aa"}}],
            "stale": [{"version": "1", PLATFORM: {"url": url, "checksum": "sha256:bb"}}],
        }
    }
    record: dict[str, object] = {
        "tools": [{"name": "stale", "version": "1", "asset": "tool_linux", "sha256": "cc"}]
    }
    assert _unverified(lock, record) == [
        "bare: no provenance in mise.lock and no recorded verification",
        "stale: the recorded verification is not of the locked artifact",
    ]


def test_zizmor_is_pinned_and_its_provenance_verified() -> None:
    """A.22: the workflow audit's scanner is pinned once, locked, and verified by mise."""
    founding = ROOT / "policies" / "founding" / "data.json"
    tools = json.loads(founding.read_text(encoding="utf-8"))["founding"]["pins"]["tools"]
    assert tools.get("zizmor") == "1.30.1", "zizmor 1.30.1 is not pinned"
    lock = tomllib.loads((ROOT / "mise.lock").read_text(encoding="utf-8"))["tools"]
    platform = lock["zizmor"][0]["platforms.linux-x64"]
    assert platform.get("provenance") == "github-attestations", platform


def test_gh_is_pinned_and_its_provenance_verified() -> None:
    """A.102: pr's GitHub CLI is pinned once, locked by tools:lock, and verified by mise."""
    founding = ROOT / "policies" / "founding" / "data.json"
    tools = json.loads(founding.read_text(encoding="utf-8"))["founding"]["pins"]["tools"]
    assert tools.get("gh") == "2.102.0", "gh 2.102.0 is not pinned"
    lock = tomllib.loads((ROOT / "mise.lock").read_text(encoding="utf-8"))["tools"]
    assert "gh" in lock, "gh is not locked"
    platform = lock["gh"][0]["platforms.linux-x64"]
    assert platform.get("provenance") == "github-attestations", platform


def test_an_npm_tool_is_verified_only_by_its_recorded_provenance(tmp_path: Path) -> None:
    """The paired negative control for npm: no record, and a record of other bytes, are named."""
    lock_dir = tmp_path / "npm-npm" / "12.2.0"
    lock_dir.mkdir(parents=True)
    aube = "packages:\n  npm@12.2.0:\n    resolution: {integrity: sha512-locked}\n"
    (lock_dir / "aube-lock.yaml").write_text(aube, encoding="utf-8")
    entry = {"version": "12.2.0", "backend": "npm:npm", "aube": {"path": str(lock_dir)}}
    lock: dict[str, object] = {"tools": {"npm:npm": [entry]}}
    kind = "npm-registry-provenance"
    stale = {"name": "npm:npm", "version": "12.2.0", "kind": kind, "integrity": "sha512-other"}
    good = {**stale, "integrity": "sha512-locked"}
    absent = ["npm:npm: an npm-backend tool with no recorded registry provenance"]
    assert _unverified(lock, {"tools": []}) == absent
    named = ["npm:npm: the recorded verification is not of the locked package"]
    assert _unverified(lock, {"tools": [stale]}) == named
    assert _unverified(lock, {"tools": [good]}) == []
