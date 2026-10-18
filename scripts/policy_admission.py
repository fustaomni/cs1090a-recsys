"""policies:admit -- a policy set is admitted only by its manifest (A.30).

A policy nothing has tested, or a file nobody listed, would be enforced all the same. So
contracts/policies.toml names each admitted domain: its directory under policies/, the root
package it owns, every policy file with its SHA-256, and its test file. A domain is admitted only
when its directory exists, every .rego in it is listed, unchanged and in its root package, its
test file is there, and opa check --strict and opa test --fail-on-empty both pass. With --plan,
one domain is judged as it stands on disk and, only if admitted, written as a source-apply spec.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from pydantic import Field

from contract_base import Contract, from_document
from spine import _run

ROOT = Path(__file__).resolve().parent.parent
POLICIES = ROOT / "policies"
MANIFEST = Path("contracts") / "policies.toml"
QUOTE = "'" * 3
USAGE = "usage: policies:admit [--plan <domain> <root> <test-file> --out <spec.toml>]"
HEADER = (
    "# contracts/policies.toml\n"
    "# policy-manifest/v1 (A.30): each admitted policy domain, its root package, every file with\n"
    "# its SHA-256, and its test file. Written by policies:admit --plan, never by hand.\n"
)
Opa = Callable[..., subprocess.CompletedProcess[str] | None]


class PolicyFile(Contract):
    """One policy file of a domain, by name, with the SHA-256 of its bytes."""

    name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Domain(Contract):
    """One admitted domain: its directory under policies/, root package, files and test file."""

    name: str = Field(min_length=1)
    root: str = Field(min_length=1)
    files: tuple[PolicyFile, ...]
    test: str = Field(min_length=1)


class Manifest(Contract):
    """policy-manifest/v1: every admitted domain, and exactly what each one contains."""

    contract: Literal["policy-manifest/v1"] = "policy-manifest/v1"
    domains: tuple[Domain, ...] = ()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("package "):
            return line.removeprefix("package ").strip()
    return None


def _file_findings(domain: Domain, folder: Path) -> list[str]:
    listed = {entry.name: entry.sha256 for entry in domain.files}
    found: list[str] = []
    for path in sorted(folder.glob("*.rego")):
        if path.name == domain.test:
            continue
        if path.name not in listed:
            found.append(f"{domain.name}: {path.name} is outside the manifest")
        elif _digest(path) != listed[path.name]:
            found.append(f"{domain.name}: {path.name} differs from its manifest digest")
        elif _package(path) != domain.root:
            found.append(f"{domain.name}: {path.name} is not in package {domain.root}")
    absent = sorted(name for name in listed if not (folder / name).is_file())
    found += [f"{domain.name}: {name} is listed but missing" for name in absent]
    return found


def _domain_findings(domain: Domain, policies: Path, opa: Opa) -> list[str]:
    folder = policies / domain.name
    if not folder.is_dir():
        return [f"{domain.name}: declared but missing"]
    found: list[str] = []
    if not (folder / domain.test).is_file():
        found.append(f"{domain.name}: its test file {domain.test} is missing")
    found += _file_findings(domain, folder)
    checked = opa("check", "--strict", str(folder))
    if checked is None or checked.returncode != 0:
        found.append(f"{domain.name}: opa check --strict refused it")
    tested = opa("test", str(folder), "--fail-on-empty")
    if tested is None or tested.returncode != 0:
        found.append(f"{domain.name}: its tests failed or ran nothing")
    return found


def findings(manifest: Manifest, policies: Path, *, opa: Opa = _run) -> list[str]:
    """Every way a declared domain falls short of admission; empty only when all are admitted."""
    names = [domain.name for domain in manifest.domains]
    found = [f"{name}: declared twice" for name in sorted(set(names)) if names.count(name) > 1]
    for domain in manifest.domains:
        found += _domain_findings(domain, policies, opa)
    return found


def load(root: Path = ROOT) -> Manifest:
    """The manifest, validated."""
    text = (root / MANIFEST).read_text(encoding="utf-8")
    return from_document(Manifest, tomllib.loads(text))


def _file_line(entry: PolicyFile) -> str:
    return f'  {{ name = {json.dumps(entry.name)}, sha256 = "{entry.sha256}" }},\n'


def render(manifest: Manifest) -> str:
    """The manifest as TOML: one [[domains]] table per admitted domain, files with digests."""
    parts = [HEADER, 'contract = "policy-manifest/v1"\n']
    for domain in manifest.domains:
        parts.append("\n[[domains]]\n")
        fields = (("name", domain.name), ("root", domain.root), ("test", domain.test))
        parts += [f"{key} = {json.dumps(value)}\n" for key, value in fields]
        parts.append("files = [\n")
        parts += [_file_line(entry) for entry in domain.files]
        parts.append("]\n")
    return "".join(parts)


def _spec(existing: str | None, text: str) -> str:
    """A source-apply spec writing the manifest: created, or replaced exactly as it stands."""
    head = f'contract = "source-apply/v1"\n\n[[operations]]\npath = "{MANIFEST.as_posix()}"\n'
    if existing is None:
        return f'{head}op = "create"\ncontent = {QUOTE}\n{text}{QUOTE}\n'
    body = f"anchor = {QUOTE}{existing}{QUOTE}\nreplacement = {QUOTE}{text}{QUOTE}\n"
    return f'{head}op = "replace"\n{body}'


def _plan(name: str, root: str, test: str, out: Path) -> int:
    folder = POLICIES / name
    files = tuple(
        PolicyFile(name=path.name, sha256=_digest(path))
        for path in sorted(folder.glob("*.rego"))
        if path.name != test
    )
    domain = Domain(name=name, root=root, files=files, test=test)
    found = findings(Manifest(domains=(domain,)), POLICIES)
    if found:
        raise SystemExit("not admitted:\n" + "\n".join(found))
    path = ROOT / MANIFEST
    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    kept = load(ROOT).domains if existing is not None else ()
    others = tuple(entry for entry in kept if entry.name != name)
    admitted = Manifest(domains=tuple(sorted((*others, domain), key=lambda d: d.name)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_spec(existing, render(admitted)), encoding="utf-8")
    print(f"admitted {name}; apply the manifest with source:apply {out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """policies:admit -- refuse any domain the manifest declares but cannot admit; or --plan."""
    args = list(sys.argv[1:] if argv is None else argv)
    match args:
        case []:
            manifest = load(ROOT)
            found = findings(manifest, POLICIES)
            if found:
                raise SystemExit("policies refused:\n" + "\n".join(found))
            print(f"{len(manifest.domains)} policy domain(s) admitted")
            return 0
        case ["--plan", name, root, test, "--out", out]:
            return _plan(name, root, test, Path(out))
        case _:
            raise SystemExit(USAGE)


if __name__ == "__main__":
    sys.exit(main())
