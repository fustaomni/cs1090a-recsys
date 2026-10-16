"""Plan a port: print a source:apply spec that brings files from another checkout (A.29).

A PLAN, NOT A WRITE. Declarative tools split plan from apply: plan reads the desired sources
and prints the change, apply makes it, and planning again prints nothing. This is the plan
half. It reads each named file from a source checkout and prints one source-apply/v1 spec on
stdout that creates the file here, as it is, and records it in contracts/provenance.toml
with the digest of the bytes it carries. It writes nothing: source:apply is the only writer.

REFUSED BEFORE ANYTHING IS PRINTED: a file already present here (there is nothing to port),
a path outside either checkout, and a Python line over 100 columns, which source:apply would
refuse anyway -- so a refusal names the file and line here, not after a failed apply.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = "contracts/provenance.toml"
LINE_LIMIT = 100


def _string(text: str) -> str:
    """A TOML basic string. JSON's string escapes are a subset TOML accepts."""
    return json.dumps(text, ensure_ascii=False)


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def build(source: Path, paths: list[str], here: Path = ROOT) -> str:
    """The spec's text, or SystemExit naming the first refusal."""
    operations: list[str] = []
    entries: list[str] = []
    for path in paths:
        origin, target = source / path, here / path
        if not (_inside(origin, source) and _inside(target, here)):
            raise SystemExit(f"{path}: outside a checkout")
        if target.exists():
            raise SystemExit(f"{path}: already present here; nothing to port")
        data = origin.read_bytes()
        text = data.decode("utf-8")
        if path.endswith(".py"):
            lines = enumerate(text.splitlines(), start=1)
            long = [number for number, line in lines if len(line) > LINE_LIMIT]
            if long:
                raise SystemExit(f"{path}: lines over {LINE_LIMIT} columns: {long}")
        operations.append(
            f'[[operations]]\nop = "create"\npath = {_string(path)}\ncontent = {_string(text)}\n'
        )
        digest = hashlib.sha256(data).hexdigest()
        entries.append(f'\n[[files]]\npath = {_string(path)}\nsha256 = "{digest}"\n')
    record = (here / PROVENANCE).read_text(encoding="utf-8")
    operations.append(
        f'[[operations]]\nop = "replace"\npath = "{PROVENANCE}"\n'
        f"anchor = {_string(record)}\nreplacement = {_string(record + ''.join(entries))}\n"
    )
    return 'contract = "source-apply/v1"\n\n' + "\n".join(operations)


def main() -> int:
    match sys.argv[1:]:
        case [source, *paths] if paths:
            print(build(Path(source), paths), end="")
            return 0
        case other:
            raise SystemExit(f"usage: source_port.py <source-checkout> <path>...  (got {other})")


if __name__ == "__main__":
    raise SystemExit(main())
