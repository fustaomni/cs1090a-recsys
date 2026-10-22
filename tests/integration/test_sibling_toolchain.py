# tests/integration/test_sibling_toolchain.py
"""A sibling's FAS mode is its own toolchain: the versions its flake.lock resolves (A.188).

The FAS mode replaces nix develop with bash and pins the flake's tools through mise. Pins copied
from elsewhere drifted on six of nine tools, and a newer regal failed the sibling's own policy
gate on files nobody changed. So each pin is proven live: nixpkgs ships that version at the
recorded revision, and mise installs it under that name. The sibling is private, so whether its
lock still pins that revision is judged on its clone, by sibling:checkout, before any trust.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from sibling_checkout import Sibling, declared

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = "https://raw.githubusercontent.com"
VERSION = re.compile(r'^\s*version\s*=\s*"([^"]+)";', re.MULTILINE)


def _fetch(url: str) -> str:
    """A public file over HTTPS; curl --fail turns an HTTP error into a failed fetch."""
    done = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "60", url],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, (url, done.stderr)
    return done.stdout


def _pinned() -> tuple[Sibling, ...]:
    siblings = tuple(s for s in declared(ROOT) if getattr(s, "nixpkgs", None))
    assert siblings, "no sibling records the nixpkgs revision its toolchain comes from"
    return siblings


def _shipped(revision: str, source: str) -> str:
    """The version nixpkgs ships: a package file's version, or a key path into a JSON file."""
    path, _, key = source.partition("#")
    text = _fetch(f"{RAW}/NixOS/nixpkgs/{revision}/{path}")
    if not key:
        found = VERSION.search(text)
        return found.group(1) if found else f"no version in {path}"
    value: object = json.loads(text)
    for part in key.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return str(value)


def _same(pin: str, version: str) -> bool:
    """mise names a JDK by vendor and release; nixpkgs by its version, which the release extends."""
    bare = pin.removeprefix("temurin-")
    return bare == version or bare.startswith((f"{version}.", f"{version}+"))


def _listed(tool: str) -> list[str]:
    done = subprocess.run(["mise", "ls-remote", tool], capture_output=True, text=True, check=False)
    return done.stdout.split()


@pytest.mark.integration
def test_every_pin_is_the_version_nixpkgs_ships() -> None:
    shipped = {
        (s.name, tool): (pin, _shipped(s.nixpkgs or "", s.packages.get(tool, "")))
        for s in _pinned()
        for tool, pin in s.tools.items()
    }
    drifted = {key: pair for key, pair in shipped.items() if not _same(*pair)}
    assert not drifted, drifted


@pytest.mark.integration
def test_every_pin_resolves_in_mise() -> None:
    pins = {tool: pin for s in _pinned() for tool, pin in s.tools.items()}
    listed = {tool: _listed(tool) for tool in pins}
    unresolved = {
        tool: [name for name in listed[tool] if name.startswith(pin.rsplit(".", 2)[0])][-6:]
        for tool, pin in pins.items()
        if pin not in listed[tool]
    }
    assert not unresolved, unresolved
