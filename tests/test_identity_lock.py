# tests/test_identity_lock.py
"""A generated project's lock takes its name with its identity (A.129).

uv.lock records the project's own package, and `uv sync --locked` refuses a lock whose root
package is named otherwise than pyproject.toml's project. The lock cannot read the declaration,
so its root line is a slot, and taking an identity rewrites it with pyproject.toml's, in one
operation and offline. Found when cs1090a-volatility's first setup refused its stale lock.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

from project_identity import DECLARATION, load, set_identity

REPO = Path(__file__).resolve().parent.parent
ROOTS = ({"virtual": "."}, {"editable": "."})


def _root_package(lock: Path) -> str:
    """The lock's own project, found by its source, never by its position."""
    packages = tomllib.loads(lock.read_text(encoding="utf-8"))["package"]
    roots = [package["name"] for package in packages if package.get("source") in ROOTS]
    assert roots, "the lock records no root package"
    return str(roots[0])


def test_taking_an_identity_renames_the_lock_root(tmp_path: Path) -> None:
    for name in ("pyproject.toml", "uv.lock", str(DECLARATION)):
        copied = tmp_path / name
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / name, copied)
    assert _root_package(tmp_path / "uv.lock") == load(REPO).name
    probe = {"name": "probe-project", "repository": "https://github.com/example/probe-project"}
    set_identity(tmp_path, load(tmp_path).model_copy(update=probe))
    assert _root_package(tmp_path / "uv.lock") == "probe-project"
