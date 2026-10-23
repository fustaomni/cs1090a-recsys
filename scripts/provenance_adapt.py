"""provenance:adapt -- a change to a ported file is planned as its recorded patch (A.85).

AN ADAPTATION IS RECORDED, NEVER HAND-WRITTEN. A file ported from cscie103 may differ from its
upstream bytes only as upstream plus a recorded patch (A.6). This task reads the upstream file
from a pinned checkout and refuses it unless it hashes to the digest provenance records, builds
the unified diff from upstream to the working file, proves in a scratch repository that
reversing it reproduces upstream exactly, and plans both writes -- the patch and its [[adapted]]
entry -- as one source-apply/v1 spec under .artifacts for source:apply. Nothing else is written.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import sys
import tempfile
import tomllib
from pathlib import Path

from gitenv import git

ROOT = Path(__file__).resolve().parent.parent
RECORD = Path("contracts") / "provenance.toml"
PATCHES = Path("contracts") / "vendor-patches"
USAGE = "usage: provenance_adapt.py --out <spec.toml> --reason <why> <upstream-checkout> <path>"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(target: Path, remedy: str) -> bytes:
    """A file's bytes, or a refusal naming it, why it cannot be read, and what to do (A.125).

    An OSError escaping here reached the task as a traceback, with no next step. Every other
    refusal in plan() is a SystemExit naming its file, so an unreadable one is refused alike.
    """
    try:
        return target.read_bytes()
    except OSError as error:
        why = error.strerror or type(error).__name__
        raise SystemExit(f"{target} cannot be read ({why}); {remedy}") from None


def _toml_string(value: str) -> str:
    """A TOML basic string, as source:port writes one: JSON's escapes are a subset TOML accepts.

    Any text survives, three single quotes and newlines included (A.124).
    """
    return json.dumps(value, ensure_ascii=False)


def _replace(path: str, anchor: str, replacement: str) -> str:
    return (
        '[[operations]]\nop = "replace"\n'
        f"path = {_toml_string(path)}\n"
        f"anchor = {_toml_string(anchor)}\n"
        f"replacement = {_toml_string(replacement)}\n"
    )


def _patch(path: str, upstream: str, local: str) -> str:
    if not upstream.endswith("\n") or not local.endswith("\n"):
        raise SystemExit(f"{path}: both versions must end with a newline to be patched")
    lines = difflib.unified_diff(
        upstream.splitlines(keepends=True),
        local.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(lines)


def reverses_to_upstream(path: str, patch: str, local: bytes, upstream_sha: str) -> bool:
    """Reversing the patch on the working bytes, in a scratch repository, gives upstream."""
    with tempfile.TemporaryDirectory() as scratch:
        base = Path(scratch)
        if git("init", "-q", str(base), cwd=base).returncode != 0:
            return False
        copy = base / path
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(local)
        (base / "adaptation.patch").write_text(patch, encoding="utf-8")
        reversed_ = git("apply", "-R", "adaptation.patch", cwd=base)
        return reversed_.returncode == 0 and _digest(copy.read_bytes()) == upstream_sha


def _adapted_blocks(text: str, path: str, header: str = "[[adapted]]") -> list[str]:
    """Every block under header recorded for path, exactly as written, blank lines or not.

    A block is its header and its path line, then key lines up to a blank line or the next table
    header: the record's later entries sit back to back, so blank lines cannot delimit them.
    """
    lines = text.splitlines(keepends=True)
    path_line = f"path = {_toml_string(path)}\n"
    blocks: list[str] = []
    for index, line in enumerate(lines):
        if line != f"{header}\n" or lines[index + 1 : index + 2] != [path_line]:
            continue
        end = index + 1
        while end < len(lines) and lines[end].strip() and not lines[end].startswith("["):
            end += 1
        blocks.append("".join(lines[index:end]))
    return blocks


def plan(root: Path, upstream: Path, path: str, reason: str) -> str:
    """The source-apply/v1 spec recording path's adaptation, after every check has held."""
    record_text = (root / RECORD).read_text(encoding="utf-8")
    record = tomllib.loads(record_text)
    files = {entry["path"]: entry for entry in record.get("files", [])}
    if path not in files:
        raise SystemExit(f"{path} is not a ported file in {RECORD}")
    # A RELOCATED PORT IS READ WHERE IT CAME FROM (A.123): upstream_path, else its own path.
    origin = str(files[path].get("upstream_path", path))
    upstream_sha = str(files[path]["sha256"])
    upstream_bytes = _read(upstream / origin, "run upstream:checkout at the pin first")
    if _digest(upstream_bytes) != upstream_sha:
        raise SystemExit(f"{upstream / origin} does not match the recorded upstream digest")
    local_bytes = _read(root / path, "the working file the patch is built from must exist")
    if local_bytes == upstream_bytes:
        raise SystemExit(f"{path} equals upstream; there is nothing to adapt")
    patch = _patch(path, upstream_bytes.decode("utf-8"), local_bytes.decode("utf-8"))
    if not reverses_to_upstream(path, patch, local_bytes, upstream_sha):
        raise SystemExit(f"{path}: the patch does not lead back to upstream; nothing planned")
    patch_path = (PATCHES / f"{path}.patch").as_posix()
    entry = (
        "[[adapted]]\n"
        f"path = {_toml_string(path)}\n"
        f"reason = {_toml_string(reason)}\n"
        f"patch = {_toml_string(patch_path)}\n"
        f"sha256 = {_toml_string(_digest(local_bytes))}\n"
    )
    existing = _adapted_blocks(record_text, path)
    if not existing:
        # AFTER THE WHOLE [[files]] BLOCK: a commit line (A.136) or upstream_path stays the port's.
        anchor = _adapted_blocks(record_text, path, "[[files]]")[0]
        record_ops = [_replace(RECORD.as_posix(), anchor, anchor + "\n" + entry)]
    else:
        record_ops = [_replace(RECORD.as_posix(), existing[0], entry)]
        record_ops += [_replace(RECORD.as_posix(), block, "") for block in existing[1:]]
    current = root / patch_path
    if current.exists():
        patch_op = _replace(patch_path, current.read_text(encoding="utf-8"), patch)
    else:
        patch_op = (
            '[[operations]]\nop = "create"\n'
            f"path = {_toml_string(patch_path)}\n"
            f"content = {_toml_string(patch)}\n"
        )
    return 'contract = "source-apply/v1"\n\n' + patch_op + "\n" + "\n".join(record_ops)


def main() -> int:
    match sys.argv[1:]:
        case ["--out", out, "--reason", reason, upstream, path]:
            if Path(out).parts[:1] != (".artifacts",):
                raise SystemExit(f"{out}: a planned spec is written only under .artifacts")
            spec = plan(ROOT, Path(upstream), path, reason)
            target = ROOT / out
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(spec, encoding="utf-8")
            print(f"planned {path}'s adaptation into {out}; apply it with source:apply {out}")
            return 0
        case other:
            raise SystemExit(f"{USAGE}  (got {other})")


if __name__ == "__main__":
    raise SystemExit(main())
