# /// script
# requires-python = "==3.12.3"
# dependencies = ["tomlkit>=0.15.1"]
# [tool.uv]
# exclude-newer = "2026-10-08T00:00:00Z"
# ///
"""Founding configuration edit for cs1090a-recsys (bootstrap tier).

Under mise's paranoid mode neither `mise use` nor `mise config set` will write an untrusted
mise.toml, so the toolchain tables are written here with tomlkit. Both files are edited in
memory, rendered, re-parsed with tomllib and checked: the intended values present, everything
else unchanged. Only then are both written (sibling temp file, fsync, os.replace, directory
fsync). --check reports and writes nothing.

Pins: each tool's newest release published before CUTOFF, resolved by mise with the full
RFC 3339 timestamp (a date-only value means end of day in mise) and proven against the
GitHub release record.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import tomlkit

CUTOFF = "2026-10-08T00:00:00Z"
MISE_ROOT: dict[str, Any] = {"min_version": "2026.10.4"}
MISE_TABLES: dict[str, dict[str, Any]] = {
    "tools": {"lefthook": "2.2.0", "opa": "1.21.1", "regal": "0.43.0", "uv": "0.12.23"},
    "settings": {"lockfile": True, "minimum_release_age": CUTOFF},
    "env": {"UV_CACHE_DIR": "{{config_root}}/.cache/uv"},
}
UV_TABLE: dict[str, Any] = {"exclude-newer": CUTOFF, "python-preference": "only-managed"}


def plain(item: Any) -> Any:
    return item.unwrap() if hasattr(item, "unwrap") else item


def put(container: Any, key: str, value: Any, where: str, changes: list[str]) -> None:
    if key in container:
        if plain(container[key]) != value:
            sys.exit(f"REFUSED: {where}.{key} is {plain(container[key])!r}, wanted {value!r}")
        return
    container[key] = value
    changes.append(f"{where}.{key} = {value!r}")


def edit(mise: Any, py: Any) -> list[str]:
    changes: list[str] = []
    for key, value in MISE_ROOT.items():
        put(mise, key, value, "mise.toml", changes)
    for name, values in MISE_TABLES.items():
        if name not in mise:
            mise[name] = tomlkit.table()
        for key, value in values.items():
            put(mise[name], key, value, f"mise.toml[{name}]", changes)
    if "uv" not in py["tool"]:
        py["tool"]["uv"] = tomlkit.table()
    for key, value in UV_TABLE.items():
        put(py["tool"]["uv"], key, value, "pyproject.toml[tool.uv]", changes)
    return changes


def verify(before_mise: dict, after_mise: dict, before_py: dict, after_py: dict) -> None:
    if after_mise.get("min_version") != MISE_ROOT["min_version"]:
        sys.exit("REFUSED: min_version is not a root key after rendering")
    expected = dict(before_mise) | MISE_ROOT
    for name, values in MISE_TABLES.items():
        expected[name] = dict(before_mise.get(name, {})) | values
    if after_mise != expected:
        sys.exit("REFUSED: mise.toml would change beyond the intended keys")
    expected_py = dict(before_py)
    expected_py["tool"] = dict(before_py["tool"])
    expected_py["tool"]["uv"] = dict(before_py["tool"].get("uv", {})) | UV_TABLE
    if after_py != expected_py:
        sys.exit("REFUSED: pyproject.toml would change beyond [tool.uv]")


def replace(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, path.stat().st_mode & 0o777)
    os.replace(tmp, path)
    dir_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    paths = {"mise": args.root / "mise.toml", "py": args.root / "pyproject.toml"}
    raw = {k: p.read_bytes() for k, p in paths.items()}
    before = {k: tomllib.loads(b.decode("utf-8")) for k, b in raw.items()}
    docs = {k: tomlkit.parse(b.decode("utf-8")) for k, b in raw.items()}
    changes = edit(docs["mise"], docs["py"])
    out = {k: tomlkit.dumps(d) for k, d in docs.items()}
    after = {k: tomllib.loads(t) for k, t in out.items()}
    verify(before["mise"], after["mise"], before["py"], after["py"])
    for line in changes or ["(no change: already converged)"]:
        print(line)
    for k, p in paths.items():
        print(
            f"{p.name}: {hashlib.sha256(raw[k]).hexdigest()} -> "
            f"{hashlib.sha256(out[k].encode()).hexdigest()}"
        )
    if args.check or not changes:
        print("CHECK: nothing written" if args.check else "NOOP_CONVERGED")
        return 0
    for k, p in paths.items():
        replace(p, out[k])
    print("APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
