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
import tomllib
from pathlib import Path

from gitenv import git

ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = "contracts/provenance.toml"
LINE_LIMIT = 100
EVIDENCE = ".artifacts"
USAGE = (
    "usage: source_port.py [--into <checkout>] [--out <file under .artifacts>]"
    " <source-checkout> <path[=local]>..."
)


def _string(text: str) -> str:
    """A TOML basic string. JSON's string escapes are a subset TOML accepts."""
    return json.dumps(text, ensure_ascii=False)


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _head(source: Path) -> str | None:
    """The commit a git checkout is at, or None for a plain directory."""
    if not (source / ".git").exists():
        return None
    found = git("rev-parse", "HEAD", cwd=source)
    return found.stdout.strip() if found.returncode == 0 else None


def build(source: Path, paths: list[str], here: Path = ROOT) -> str:
    """The spec's text, or SystemExit naming the first refusal."""
    operations: list[str] = []
    entries: list[str] = []
    # THE CANONICAL SOURCE KEEPS NO PORT RECORD (A.217): its files are its own, so a port into
    # it creates them and records nothing; a sibling's record is kept exactly as before.
    recorded = (here / PROVENANCE).exists()
    record = (here / PROVENANCE).read_text(encoding="utf-8") if recorded else ""
    pinned = tomllib.loads(record).get("commit") if recorded else None
    head = _head(source)
    # A FILE READ AT ANOTHER COMMIT SAYS SO (A.136); the record's own commit stays the default.
    at = f'commit = "{head}"\n' if head is not None and head != pinned else ""
    for spec in paths:
        # A PORT MAY LAND ELSEWHERE (A.123): upstream=local records the path it came from.
        upstream_path, _, local = spec.partition("=")
        path = local or upstream_path
        origin, target = source / upstream_path, here / path
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
        moved = f"upstream_path = {_string(upstream_path)}\n" if path != upstream_path else ""
        entries.append(f'\n[[files]]\npath = {_string(path)}\n{moved}sha256 = "{digest}"\n{at}')
    if recorded:
        operations.append(
            f'[[operations]]\nop = "replace"\npath = "{PROVENANCE}"\n'
            f"anchor = {_string(record)}\nreplacement = {_string(record + ''.join(entries))}\n"
        )
    return 'contract = "source-apply/v1"\n\n' + "\n".join(operations)


def _save(here: Path, out: str, source: str, paths: list[str]) -> int:
    """Save the plan under here's .artifacts, where here's own source:apply reads it."""
    target = here / out
    if not _inside(target, here / EVIDENCE):
        raise SystemExit(f"--out must be under {EVIDENCE}, where evidence lives: {out}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build(Path(source), paths, here), encoding="utf-8")
    print(f"planned {len(paths)} file(s) into {out}; apply it with source:apply {out}")
    return 0


def main() -> int:
    """Print the plan, or save it with --out: a saved plan is applied exactly as reviewed.

    THE SAVED PLAN. The run gateway writes its run summary to the same stdout, so a piped spec
    would end in a line that is not TOML. As with `terraform plan -out`, the plan is saved as a
    file and `source:apply <file>` applies that exact file. It is saved under .artifacts, where
    evidence lives and git does not look, and nowhere else.
    """
    match sys.argv[1:]:
        case ["--into", into, "--out", out, source, *paths] if paths:
            return _save(Path(into), out, source, paths)
        case ["--into", into, source, *paths] if paths:
            print(build(Path(source), paths, Path(into)), end="")
            return 0
        case ["--out", out, source, *paths] if paths:
            return _save(ROOT, out, source, paths)
        case [source, *paths] if paths:
            print(build(Path(source), paths, ROOT), end="")
            return 0
        case other:
            raise SystemExit(f"{USAGE}  (got {other})")


if __name__ == "__main__":
    raise SystemExit(main())
