"""sibling:pin -- a sibling's FAS pins, generated from its own flake.lock (A.203).

A sibling's FAS mode pins, through mise, the tools its flake would otherwise take from nixpkgs.
Each pin is derived data: the version nixpkgs ships at the revision the sibling's flake.lock
pins, named as the one version mise lists for it. Retyped pins drifted (A.185, A.188), so they
are generated here, and a moved lock is regenerated, never edited by hand. A source with no
version, a version mise does not list, and an ambiguous match are refused by name before
anything is planned. The plan is a source:apply spec, so the write is judged like any other.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import unquote

from sibling_checkout import ROOT, Sibling, _locked_nixpkgs, _siblings_parent, declared

RAW = "https://raw.githubusercontent.com"
VERSION = re.compile(r'^\s*version\s*=\s*"([^"]+)";', re.MULTILINE)
RELEASE_TAG = re.compile(r"/download/jdk-([^/]+)/")
SECONDS = 60
REGISTER = "contracts/siblings.toml"
USAGE = "usage: mise run run sibling:pin <name> (--out <spec.toml> | --check)"

Fetch = Callable[[str], str]
Listing = Callable[[str, str], list[str]]


def fetch(url: str) -> str:
    """A public file over HTTPS, bounded; a failed fetch is refused by its URL."""
    done = subprocess.run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--max-time",
            str(SECONDS),
            url,
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise SystemExit(f"cannot fetch {url}: {done.stderr.strip()}")
    return done.stdout


def _semver(release: str) -> str:
    """Adoptium's semver for a release: a point release's fourth number joins its build.

    Semver has three numbers, so Adoptium names jdk-17.0.20.1+1 as 17.0.20+101 (the fourth
    number times 100, plus the build), and mise lists Temurin by that name. Any other shape
    is returned unchanged, for resolve to judge against what mise lists.
    """
    numbers, plus, build = release.partition("+")
    parts = numbers.split(".")
    if len(parts) != 4 or not plus or not build.isdigit() or not parts[3].isdigit():
        return release
    return f"{'.'.join(parts[:3])}+{int(parts[3]) * 100 + int(build)}"


def shipped(revision: str, source: str, fetch: Fetch = fetch) -> str:
    """The version nixpkgs ships at revision: a package file's, or a key path into JSON."""
    path, _, key = source.partition("#")
    text = fetch(f"{RAW}/NixOS/nixpkgs/{revision}/{path}")
    if not key:
        found = VERSION.search(text)
        if found is None:
            raise SystemExit(f"{path} at {revision[:12]} declares no version")
        return found.group(1)
    value: object = json.loads(text)
    for part in key.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    # A JDK ENTRY (A.203): its url is the asset nix downloads, and that url's release tag names
    # the exact release. version and build are parsed and can drop a point release's fourth
    # number, so they are composed only when no tag is recorded.
    if isinstance(value, dict) and isinstance(value.get("version"), str):
        tag = RELEASE_TAG.search(str(value.get("url", "")))
        build = value.get("build")
        if tag is not None:
            value = _semver(unquote(tag.group(1)))
        else:
            value = f"{value['version']}+{build}" if build else value["version"]
    if not isinstance(value, str):
        raise SystemExit(f"{path} at {revision[:12]} holds no version at {key}")
    return value


def listed(tool: str, prefix: str = "") -> list[str]:
    """The versions mise lists for tool, bounded; a listing mise cannot make is refused."""
    # THE SIBLING'S CATALOGUE, NOT THIS REPOSITORY'S COOLDOWN (A.203): a pin mirrors
    # the sibling's reviewed flake and is an exact version, which minimum_release_age
    # does not filter at install, so mise is asked unfiltered; 0s disables the cutoff.
    command = ["mise", "ls-remote", "--json", "--minimum-release-age", "0s", tool]
    command += [prefix] if prefix else []
    try:
        done = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(f"mise could not list {tool} within {SECONDS}s") from None
    if done.returncode != 0:
        raise SystemExit(f"mise could not list {tool}: {done.stderr.strip()}")
    return [str(entry["version"]) for entry in json.loads(done.stdout)]


def same(pin: str, version: str) -> bool:
    """mise names a JDK by vendor and release; nixpkgs by its version, which the release extends."""
    bare = pin.removeprefix("temurin-")
    return bare == version or bare.startswith((f"{version}.", f"{version}+"))


def resolve(tool: str, version: str, listed: Sequence[str]) -> str:
    """The one version mise lists that is what nixpkgs ships; none or several is refused."""
    if version in listed:
        return version
    fits = [name for name in listed if same(name, version)]
    if len(fits) == 1:
        return fits[0]
    if not fits:
        raise SystemExit(f"{tool}: nixpkgs ships {version}; mise lists no version matching it")
    raise SystemExit(f"{tool}: nixpkgs ships {version}, matched by several: {', '.join(fits)}")


def pins(
    sibling: Sibling, revision: str, *, fetch: Fetch = fetch, listing: Listing = listed
) -> dict[str, str]:
    """Every pin of the sibling, generated at revision from its packages' sources."""
    return {
        tool: resolve(tool, shipped(revision, source, fetch), listing(tool, ""))
        for tool, source in sorted(sibling.packages.items())
    }


def stale(sibling: Sibling, revision: str, computed: dict[str, str]) -> tuple[str, ...]:
    """The moved revision, then every pin that differs from its generated value."""
    moved = ("nixpkgs",) if sibling.nixpkgs != revision else ()
    changed = tuple(tool for tool in sorted(computed) if sibling.tools.get(tool) != computed[tool])
    return moved + changed


def _replace(anchor: str, replacement: str) -> str:
    return "\n".join(
        [
            "[[operations]]",
            'op = "replace"',
            f"path = {json.dumps(REGISTER)}",
            f"anchor = {json.dumps(anchor)}",
            f"replacement = {json.dumps(replacement)}",
            "",
        ]
    )


def plan(
    sibling: Sibling,
    revision: str,
    out: Path,
    *,
    fetch: Fetch = fetch,
    listing: Listing = listed,
) -> tuple[str, ...]:
    """Generate every pin first, then plan the register's changed lines as a source:apply spec."""
    computed = pins(sibling, revision, fetch=fetch, listing=listing)
    moved = stale(sibling, revision, computed)
    operations = []
    if "nixpkgs" in moved:
        operations.append(_replace(f'nixpkgs = "{sibling.nixpkgs}"', f'nixpkgs = "{revision}"'))
    for tool in moved:
        if tool != "nixpkgs":
            old, new = sibling.tools[tool], computed[tool]
            operations.append(_replace(f'{tool} = "{old}"', f'{tool} = "{new}"'))
    if operations:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('contract = "source-apply/v1"\n\n' + "\n".join(operations), "utf-8")
    return moved


def main(argv: Sequence[str] | None = None) -> int:
    """sibling:pin <name> --out <spec.toml> plans the regenerated pins; --check names stale ones."""
    match list(sys.argv[1:] if argv is None else argv):
        case [name, "--check"]:
            out = None
        case [name, "--out", path]:
            out = Path(path)
        case other:
            raise SystemExit(f"{USAGE}  (got {other})")
    sibling = next((each for each in declared(ROOT) if each.name == name), None)
    if sibling is None:
        raise SystemExit(f"{name} is not a sibling contracts/siblings.toml declares")
    revision = _locked_nixpkgs(_siblings_parent() / sibling.name)
    if revision is None:
        raise SystemExit(f"{name}'s clone pins no nixpkgs: check it out with sibling:checkout")
    if out is None:
        moved = stale(sibling, revision, pins(sibling, revision))
        if moved:
            raise SystemExit(f"{name} is stale at {revision[:12]}: {', '.join(moved)}")
        print(f"{name}: every pin is what its flake.lock resolves at {revision[:12]}")
        return 0
    moved = plan(sibling, revision, out)
    if not moved:
        print(f"{name}: already current at {revision[:12]}; nothing planned")
        return 0
    print(f"{name}: planned {', '.join(moved)} into {out}; apply it with source:apply {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
