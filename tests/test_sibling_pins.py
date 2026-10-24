"""A sibling's FAS pins are generated from its own flake.lock, never retyped (A.203).

Each pin is the one version mise lists that matches what nixpkgs ships at the revision the
sibling's flake.lock pins: a package file's version, or a key path into a JSON file. A source
with no version, a version mise does not list, and an ambiguous match are each refused by name,
so nothing is planned from a guess; a check names each stale pin. The fetch and the mise listing
are injected, so every proof here runs offline.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from sibling_checkout import Sibling

REVISION = "b" * 40
UV = "pkgs/by-name/uv/uv/package.nix"
JAVA = "pkgs/development/compilers/temurin-bin/sources.json#hotspot.linux.jdk.openjdk17.x86_64"
RELEASES = "https://github.com/adoptium/temurin17-binaries/releases/download/"
X86_64 = {
    "build": "1",
    "url": RELEASES + "jdk-17.0.20.1%2B1/OpenJDK17U-jdk_x64_linux_hotspot_17.0.20.1_1.tar.gz",
    "version": "17.0.20",
}
SOURCES = json.dumps({"hotspot": {"linux": {"jdk": {"openjdk17": {"x86_64": X86_64}}}}})


def _pins() -> ModuleType:
    found = importlib.util.find_spec("sibling_pins")
    assert found is not None, "sibling:pin does not generate a sibling's pins yet"
    return importlib.import_module("sibling_pins")


def _sibling(nixpkgs: str, tools: dict[str, str]) -> Sibling:
    """The demo sibling: its recorded revision, these pins, and uv and regal's sources."""
    packages = {"uv": UV, "regal": "pkgs/by-name/re/regal/package.nix"}
    return Sibling(
        name="demo",
        source="https://example.invalid/demo",
        tools=tools,
        nixpkgs=nixpkgs,
        packages={tool: packages[tool] for tool in tools},
    )


def test_a_source_without_a_version_is_refused_not_written(tmp_path: Path) -> None:
    """A package file with no version stops the plan, naming the file; nothing is written."""
    pins = _pins()
    out = tmp_path / "plan.toml"
    with pytest.raises(SystemExit) as refused:
        pins.plan(
            _sibling("a" * 40, {"uv": "0.12.22"}),
            REVISION,
            out,
            fetch=lambda url: "{ }\n",
            listing=lambda tool, prefix: ["0.12.23"],
        )
    assert UV in str(refused.value), refused.value
    assert not out.exists(), "a plan was written from a source with no version"


def test_the_java_pin_is_the_one_temurin_release_nixpkgs_matches() -> None:
    """nixpkgs downloads 17.0.20.1+1, which Adoptium's semver and mise name 17.0.20+101."""
    pins = _pins()
    version = pins.shipped(REVISION, JAVA, fetch=lambda url: SOURCES)
    assert version == "17.0.20+101", version
    listed = ["temurin-17.0.19+10", "temurin-17.0.20+8", "temurin-17.0.20+101", "zulu-17.0.20"]
    assert pins.resolve("java", version, listed) == "temurin-17.0.20+101"


def test_a_version_mise_does_not_list_is_refused() -> None:
    """What nixpkgs ships but mise cannot install is refused, naming the tool and the version."""
    pins = _pins()
    with pytest.raises(SystemExit) as refused:
        pins.resolve("uv", "0.13.0", ["0.12.22", "0.12.23"])
    message = str(refused.value)
    assert "uv" in message, message
    assert "0.13.0" in message, message


def test_an_ambiguous_match_is_refused() -> None:
    """A version that two listed releases both extend is refused, naming both, never guessed."""
    pins = _pins()
    with pytest.raises(SystemExit) as refused:
        pins.resolve("regal", "0.42", ["0.42.0", "0.42.1"])
    message = str(refused.value)
    assert "0.42.0" in message, message
    assert "0.42.1" in message, message


def test_check_names_each_stale_pin() -> None:
    """A moved revision and every pin that differs from its generated value are named."""
    pins = _pins()
    sibling = _sibling("a" * 40, {"uv": "0.12.22", "regal": "0.42.0"})
    computed = {"uv": "0.12.23", "regal": "0.42.0"}
    assert pins.stale(sibling, REVISION, computed) == ("nixpkgs", "uv")


def test_check_passes_when_every_pin_is_current() -> None:
    """Nothing is named when the revision and every pin are what the lock resolves."""
    pins = _pins()
    sibling = _sibling(REVISION, {"uv": "0.12.23", "regal": "0.42.0"})
    computed = {"uv": "0.12.23", "regal": "0.42.0"}
    assert pins.stale(sibling, REVISION, computed) == ()


def test_the_listing_ignores_this_repository_release_age(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pin mirrors the sibling's own flake, so this repository's cooldown hides no version."""
    pins = _pins()
    seen: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        seen.append(list(command))
        return subprocess.CompletedProcess(command, 0, '[{"version": "2.7.0"}]', "")

    monkeypatch.setattr(subprocess, "run", run)
    assert pins.listed("osv-scanner") == ["2.7.0"]
    command = seen[0]
    assert "--minimum-release-age" in command, command
    assert command[command.index("--minimum-release-age") + 1] == "0s", command
