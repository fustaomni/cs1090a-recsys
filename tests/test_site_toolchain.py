# tests/test_site_toolchain.py
"""The site's package manager is npm 12, pinned and enforced, running only reviewed scripts (A.255).

npm 12 blocks dependency install scripts unless package.json's allowScripts lists them, pinned to
the version reviewed. The proof reads the declarations and the lock, so a new scripted dependency
or a version bump fails here until it is reviewed, and nothing may resolve outside the registry.
"""

from __future__ import annotations

import ast
import json
import tomllib
from pathlib import Path
from typing import Any

from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
NPM = "12.2.0"
REGISTRY = "https://registry.npmjs.org/"


def _json(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def test_the_site_installs_under_npm_12_with_only_reviewed_install_scripts() -> None:
    config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
    tools = config["tools"]
    assert tools.get("npm:npm") == NPM, tools
    # NPM 12 COMES FIRST ON PATH: mise orders tools as declared, and node's own bin has npm 11.
    order = list(tools)
    assert order.index("npm:npm") < order.index("node"), order
    # NOTHING OVERRIDES [tools]: an explicit node@ argument would go first on PATH.
    runs = [str(task.get("run", "")) for task in nonempty(list(config["tasks"].values()))]
    overriding = [run for run in runs if "node@" in run]
    assert overriding == [], overriding
    pinned = [
        path.name
        for path in nonempty(sorted((ROOT / "scripts").glob("*.py")))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and str(node.value).startswith("node@")
    ]
    assert pinned == [], pinned
    package = _json(SITE / "package.json")
    engine = package.get("devEngines", {}).get("packageManager")
    assert engine == {"name": "npm", "version": NPM, "onFail": "error"}, engine
    locked = _json(SITE / "package-lock.json")["packages"]
    scripted = sorted(
        {
            (path.split("node_modules/")[-1], entry["version"])
            for path, entry in locked.items()
            if entry.get("hasInstallScript")
        }
    )
    allowed: dict[str, bool] = package.get("allowScripts", {})
    # EVERY SCRIPTED PACKAGE IS REVIEWED: its exact version approved, or its name denied.
    for name, version in nonempty(scripted):
        reviewed = allowed.get(f"{name}@{version}") is True or allowed.get(name) is False
        assert reviewed, (name, version, allowed)
    names = {name for name, _ in scripted}
    stale = sorted(
        key for key in allowed if key not in names and key.rpartition("@")[0] not in names
    )
    assert stale == [], stale
    remote = sorted(
        path
        for path, entry in locked.items()
        if path and not str(entry.get("resolved", REGISTRY)).startswith(REGISTRY)
    )
    assert remote == [], remote
