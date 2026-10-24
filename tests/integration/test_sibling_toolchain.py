# tests/integration/test_sibling_toolchain.py
"""A sibling's FAS mode is its own toolchain: the versions its flake.lock resolves (A.188).

The FAS mode replaces nix develop with bash and pins the flake's tools through mise. Pins copied
from elsewhere drifted on six of nine tools, and a newer regal failed the sibling's own policy
gate on files nobody changed. So each pin is proven live: nixpkgs ships that version at the
recorded revision, and mise installs it under that name. The sibling is private, so whether its
lock still pins that revision is judged on its clone, by sibling:checkout, before any trust.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import sibling_pins
from sibling_checkout import Sibling, declared

ROOT = Path(__file__).resolve().parent.parent.parent


def _pinned() -> tuple[Sibling, ...]:
    siblings = tuple(s for s in declared(ROOT) if getattr(s, "nixpkgs", None))
    assert siblings, "no sibling records the nixpkgs revision its toolchain comes from"
    return siblings


@pytest.mark.integration
def test_every_pin_is_the_version_nixpkgs_ships() -> None:
    shipped = {
        (s.name, tool): (pin, sibling_pins.shipped(s.nixpkgs or "", s.packages.get(tool, "")))
        for s in _pinned()
        for tool, pin in s.tools.items()
    }
    drifted = {key: pair for key, pair in shipped.items() if not sibling_pins.same(*pair)}
    assert not drifted, drifted


@pytest.mark.integration
def test_every_pin_resolves_in_mise() -> None:
    pins = {tool: pin for s in _pinned() for tool, pin in s.tools.items()}
    listed = {tool: sibling_pins.listed(tool) for tool in pins}
    unresolved = {
        tool: [name for name in listed[tool] if name.startswith(pin.rsplit(".", 2)[0])][-6:]
        for tool, pin in pins.items()
        if pin not in listed[tool]
    }
    assert not unresolved, unresolved
