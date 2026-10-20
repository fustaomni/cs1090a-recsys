# tests/test_provenance.py
"""Every ported file is its upstream bytes, or upstream plus its recorded patch (plan A.6).

contracts/provenance.toml records each file's upstream digest at cscie103 58af9d3, and each
adapted file's patch and local digest. Proven offline on every run: an unchanged port hashes
to its upstream digest; an adapted file hashes to its recorded digest, and reversing its patch
reproduces the upstream digest exactly; a withdrawn file is absent. No network, no upstream
copy: the record is the evidence, and this test is what keeps it true.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tomllib
from pathlib import Path

from gitenv import scrubbed_env
from nonvacuous import nonempty
from provenance_adapt import plan

ROOT = Path(__file__).resolve().parent.parent
RECORD = tomllib.loads((ROOT / "contracts" / "provenance.toml").read_text(encoding="utf-8"))


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entries(record: dict[str, object], key: str) -> list[dict[str, str]]:
    raw = record.get(key, [])
    assert isinstance(raw, list), key
    return [{str(k): str(v) for k, v in item.items()} for item in raw if isinstance(item, dict)]


def _unproven(root: Path, record: dict[str, object], scratch: Path) -> list[str]:
    """Every recorded file that does not satisfy its rule, with the reason."""
    adapted = {entry["path"]: entry for entry in _entries(record, "adapted")}
    withdrawn = {entry["path"] for entry in _entries(record, "withdrawn")}
    subprocess.run(["git", "init", "-q", str(scratch)], env=scrubbed_env(), check=True)
    problems: list[str] = []
    for entry in _entries(record, "files"):
        path, upstream = entry["path"], entry["sha256"]
        local = root / path
        if path in withdrawn:
            if local.exists():
                problems.append(f"{path}: withdrawn but present")
            continue
        if not local.is_file():
            problems.append(f"{path}: missing")
            continue
        if path not in adapted:
            if _digest(local.read_bytes()) != upstream:
                problems.append(f"{path}: differs from upstream with no recorded patch")
            continue
        if _digest(local.read_bytes()) != adapted[path]["sha256"]:
            problems.append(f"{path}: differs from its recorded adaptation")
            continue
        copy = scratch / path
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, copy)
        patch = root / adapted[path]["patch"]
        reversed_ = subprocess.run(
            ["git", "apply", "-R", str(patch)],
            cwd=scratch,
            env=scrubbed_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        if reversed_.returncode != 0 or _digest(copy.read_bytes()) != upstream:
            problems.append(f"{path}: its patch does not lead back to upstream")
    return sorted(problems)


def test_every_adapted_file_is_upstream_plus_its_patch(tmp_path: Path) -> None:
    assert _entries(RECORD, "files"), "provenance records no files: nothing would be proven"
    problems = _unproven(ROOT, RECORD, tmp_path / "scratch")
    assert not problems, "provenance does not hold: " + "; ".join(problems)


def test_a_drifted_port_is_named(tmp_path: Path) -> None:
    """The paired negative control: drift of each kind is named, so the proof cannot pass empty."""
    root = tmp_path / "root"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "a.py").write_text("changed\n", encoding="utf-8")
    (root / "scripts" / "b.py").write_text("adapted\n", encoding="utf-8")
    (root / "b.patch").write_text("not a patch\n", encoding="utf-8")
    record: dict[str, object] = {
        "files": [
            {"path": "scripts/a.py", "sha256": _digest(b"upstream\n")},
            {"path": "scripts/b.py", "sha256": _digest(b"upstream\n")},
        ],
        "adapted": [
            {"path": "scripts/b.py", "patch": "b.patch", "sha256": _digest(b"adapted\n")},
        ],
    }
    assert _unproven(root, record, tmp_path / "scratch") == [
        "scripts/a.py: differs from upstream with no recorded patch",
        "scripts/b.py: its patch does not lead back to upstream",
    ]


def _applied(root: Path, spec: str) -> None:
    """The operations provenance:adapt plans, applied in order as source:apply would."""
    for operation in nonempty(tomllib.loads(spec)["operations"]):
        target = root / operation["path"]
        if operation["op"] == "create":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(operation["content"], encoding="utf-8")
        else:
            text = target.read_text(encoding="utf-8")
            assert text.count(operation["anchor"]) == 1, operation["anchor"]
            replaced = text.replace(operation["anchor"], operation["replacement"])
            target.write_text(replaced, encoding="utf-8")


def _ported(tmp_path: Path, block: str) -> tuple[Path, Path]:
    """An upstream checkout holding tests/t.py, and a root whose record is `block`."""
    upstream, root = tmp_path / "upstream", tmp_path / "root"
    (upstream / "tests").mkdir(parents=True)
    (upstream / "tests" / "t.py").write_text("x = 1\n", encoding="utf-8")
    (root / "contracts").mkdir(parents=True)
    (root / "contracts" / "provenance.toml").write_text(block, encoding="utf-8")
    return upstream, root


def test_a_relocated_port_reverses_to_its_upstream_path(tmp_path: Path) -> None:
    """A.123: adapted where it now lives, its patch still leads back to the upstream bytes."""
    upstream_sha = _digest(b"x = 1\n")
    block = (
        f'[[files]]\npath = "tests/integration/t.py"\nupstream_path = "tests/t.py"\n'
        f'sha256 = "{upstream_sha}"\n'
    )
    upstream, root = _ported(tmp_path, block)
    (root / "tests" / "integration").mkdir(parents=True)
    (root / "tests" / "integration" / "t.py").write_text("x = 2\n", encoding="utf-8")
    _applied(root, plan(root, upstream, "tests/integration/t.py", "moved"))
    record = tomllib.loads((root / "contracts" / "provenance.toml").read_text(encoding="utf-8"))
    assert _unproven(root, record, tmp_path / "scratch") == []


def test_an_adaptation_follows_its_files_entry_whole(tmp_path: Path) -> None:
    """A commit line after sha256 (A.136) stays the port's, never the adaptation's."""
    upstream_sha = _digest(b"x = 1\n")
    commit = "0" * 40
    block = f'[[files]]\npath = "tests/t.py"\nsha256 = "{upstream_sha}"\ncommit = "{commit}"\n'
    upstream, root = _ported(tmp_path, block)
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "t.py").write_text("x = 2\n", encoding="utf-8")
    _applied(root, plan(root, upstream, "tests/t.py", "changed"))
    record = tomllib.loads((root / "contracts" / "provenance.toml").read_text(encoding="utf-8"))
    assert record["files"][0]["commit"] == commit
    assert "commit" not in record["adapted"][0], record["adapted"]
