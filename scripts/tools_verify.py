# scripts/tools_verify.py
"""tools:verify -- a locked tool without mise provenance, verified its publisher's way (A.279).

mise.lock records slsa, cosign, minisign or github-attestations when its backend verified one.
Every other locked tool is verified here by its publisher's own method: a GitHub release asset by
gh release verify-asset; node by a release key's OpenPGP signature on SHASUMS256.txt, checked with
pysequoia against nodejs/release-keys at a pinned commit, its signed digest equal to the lock's;
an npm package by npm audit signatures, its registry signature and attestation verified.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml
from pysequoia import Cert, Sig, verify

import upstream
from bounded import Exited, run

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "mise.lock"
RECORD = ROOT / "contracts" / "tool-provenance.toml"
SCRATCH = ROOT / ".artifacts" / "tools-verify"
PLATFORM = "platforms.linux-x64"
MISE_KINDS = frozenset({"slsa", "cosign", "minisign", "github-attestations"})
# NODE SIGNS WITH THE KEYS IT PUBLISHES in nodejs/release-keys, read here at a pinned commit.
KEYS_SOURCE = "https://github.com/nodejs/release-keys"
KEYS_COMMIT = "481637f813e912c4aa3622d7964ab426c97b8e8d"
DEADLINE = 600.0


def node_signer(shasums: bytes, signature: bytes, keys: Sequence[Cert]) -> str:
    """The fingerprint of the key whose detached signature on SHASUMS256.txt verifies, else ''."""

    def store(_key_ids: list[str]) -> list[Cert]:
        return list(keys)

    try:
        verified = verify(bytes=shasums, store=store, signature=Sig.from_bytes(signature))
    except RuntimeError:
        return ""
    return str(verified.valid_sigs[0].certificate) if verified.valid_sigs else ""


def signed_sha256(shasums: bytes, asset: str) -> str:
    """The digest SHASUMS256.txt signs for asset, else ''."""
    for line in shasums.decode("utf-8").splitlines():
        digest, _, name = line.partition("  ")
        if name == asset:
            return digest
    return ""


def npm_audited(report: str, name: str, version: str) -> bool:
    """Whether npm audit signatures --json verified name@version's signature and attestation."""
    data = json.loads(report)
    if data.get("invalid") or data.get("missing"):
        return False
    return any(
        entry.get("name") == name and entry.get("version") == version and entry.get("attestations")
        for entry in data.get("verified", [])
    )


def github_asset(url: str) -> tuple[str, str, str]:
    """(repository, tag, asset) named by a GitHub release download URL."""
    owner, repository, _releases, _download, tag, asset = url.removeprefix(
        "https://github.com/"
    ).split("/")
    return f"{owner}/{repository}", tag, asset


def aube_integrity(lock_dir: Path, package: str, version: str) -> str:
    """The integrity the aube lock mise wrote records for package@version."""
    document = yaml.safe_load((lock_dir / "aube-lock.yaml").read_text(encoding="utf-8"))
    return str(document["packages"][f"{package}@{version}"]["resolution"]["integrity"])


def _ran(argv: Sequence[str], cwd: Path) -> str:
    """The output of a command that must succeed, or a refusal naming it."""
    done = run(argv, deadline=DEADLINE, cwd=cwd)
    if not (isinstance(done.termination, Exited) and done.termination.code == 0):
        raise SystemExit(f"{' '.join(argv)} failed: {done.stderr.strip()[-500:]}")
    return done.stdout


def _node(entry: dict[str, Any]) -> dict[str, str]:
    """Node's tarball: a release key signed SHASUMS256.txt, and it signs the locked digest."""
    platform = entry[PLATFORM]
    base, asset = str(platform["url"]).rsplit("/", 1)
    here = SCRATCH / "node"
    here.mkdir(parents=True, exist_ok=True)
    for name in ("SHASUMS256.txt", "SHASUMS256.txt.sig"):
        _ran(["curl", "-fsSL", "-o", str(here / name), f"{base}/{name}"], here)
    keys_dir = upstream.checkout(KEYS_SOURCE, KEYS_COMMIT) / "keys"
    keys = [Cert.from_file(str(path)) for path in sorted(keys_dir.glob("*.asc"))]
    shasums = (here / "SHASUMS256.txt").read_bytes()
    signer = node_signer(shasums, (here / "SHASUMS256.txt.sig").read_bytes(), keys)
    digest = signed_sha256(shasums, asset)
    if not signer or f"sha256:{digest}" != platform["checksum"]:
        raise SystemExit(f"node: {asset} is not signed by a release key with the locked digest")
    return {
        "kind": "nodejs-release-signature",
        "asset": asset,
        "sha256": digest,
        "signer": signer,
        "keys": f"nodejs/release-keys@{KEYS_COMMIT}",
    }


def _github(entry: dict[str, Any]) -> dict[str, str]:
    """A GitHub release asset: GitHub attests it, and its digest is the locked one."""
    platform = entry[PLATFORM]
    repository, tag, asset = github_asset(str(platform["url"]))
    here = SCRATCH / "github" / repository.replace("/", "-")
    here.mkdir(parents=True, exist_ok=True)
    download = ["gh", "release", "download", tag, "--pattern", asset, "--repo", repository]
    _ran([*download, "--dir", str(here), "--clobber"], here)
    _ran(["gh", "release", "verify-asset", tag, str(here / asset), "--repo", repository], here)
    digest = hashlib.sha256((here / asset).read_bytes()).hexdigest()
    if f"sha256:{digest}" != platform["checksum"]:
        raise SystemExit(f"{repository}: {asset} differs from the locked digest")
    return {"kind": "github-immutable-release", "asset": asset, "sha256": digest}


def _npm(name: str, entry: dict[str, Any]) -> dict[str, str]:
    """An npm package: registry signature and attestation verified, at the locked integrity."""
    package, version = name.removeprefix("npm:"), str(entry["version"])
    integrity = aube_integrity(ROOT / str(entry["aube"]["path"]), package, version)
    here = SCRATCH / "npm" / package
    here.mkdir(parents=True, exist_ok=True)
    manifest = '{"name": "tools-verify", "private": true}\n'
    (here / "package.json").write_text(manifest, encoding="utf-8")
    npm = ["mise", "exec", "--", "npm"]
    install = ["install", f"{package}@{version}", "--ignore-scripts", "--no-audit", "--no-fund"]
    _ran([*npm, *install], here)
    report = _ran([*npm, "audit", "signatures", "--json", "--include-attestations"], here)
    published = _ran([*npm, "view", f"{package}@{version}", "dist.integrity"], here).strip()
    if not npm_audited(report, package, version) or published != integrity:
        raise SystemExit(f"{name}: {package}@{version} is not verified at the locked integrity")
    return {"kind": "npm-registry-provenance", "integrity": integrity}


def _record(results: Sequence[dict[str, str]]) -> str:
    """contracts/tool-provenance.toml: every verification, one [[tools]] table each."""
    lines = [
        "# contracts/tool-provenance.toml",
        "# tool-provenance/v1 (A.9, A.279), written by tools:verify.",
        "# Each locked tool mise records no provenance for, verified by its publisher's method;",
        "# test_tool_provenance binds this record to mise.lock.",
        'contract = "tool-provenance/v1"',
        "",
    ]
    for result in results:
        lines.append("[[tools]]")
        lines.extend(f'{key} = "{value}"' for key, value in result.items())
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Verify every locked tool without mise provenance, then record every verification."""
    lock = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    tools: dict[str, list[dict[str, Any]]] = lock["tools"]
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    results: list[dict[str, str]] = []
    for name, entries in sorted(tools.items()):
        entry = entries[0]
        platform = entry.get(PLATFORM, {})
        backend = str(entry.get("backend", ""))
        if platform.get("provenance") in MISE_KINDS:
            continue
        if backend.startswith("npm:"):
            found = _npm(name, entry)
        elif backend == "core:node":
            found = _node(entry)
        elif str(platform.get("url", "")).startswith("https://github.com/"):
            found = _github(entry)
        else:
            raise SystemExit(f"{name}: no publisher method for backend {backend!r}")
        version = str(entry["version"])
        results.append({"name": name, "version": version, **found, "verified": today})
        print(f"{name} {version}: {found['kind']} verified")
    RECORD.write_text(_record(results), encoding="utf-8")
    print(f"recorded {len(results)} verification(s) in contracts/{RECORD.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
