"""Every listed safeguard is proven by a test that kills its mutant (A.52).

A trial runs the proof on the code as it is and on an unmutated scratch copy, then on the copy
with the guard's mutation: killed only if the proof passes twice and then fails. Runs are faked.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from safeguards import Safeguard, copy_committable, trial

PROOF = "tests/test_guard.py::test_guard_holds"


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    (root / "guard.rego").write_text("\tnot input.allowed\n", encoding="utf-8")
    return root


def _safeguard(proof: str = PROOF, anchor: str = "\tnot input.allowed\n") -> Safeguard:
    return Safeguard(
        id="G.1",
        engine="probe",
        guard="ERR_PROBE",
        path="guard.rego",
        anchor=anchor,
        mutant="\tfalse\n",
        proof=proof,
    )


def _copy(root: Path, destination: Path) -> None:
    shutil.copytree(root, destination, dirs_exist_ok=True)


def _killing(base: Path, _node: str) -> str:
    return "failed" if "false" in (base / "guard.rego").read_text(encoding="utf-8") else "passed"


def _blind(_base: Path, _node: str) -> str:
    return "passed"


def test_a_listed_safeguard_without_a_killing_proof_is_refused(tmp_path: Path) -> None:
    root = _root(tmp_path)
    assert trial(_safeguard(), root, _killing, _copy).verdict == "killed"
    assert trial(_safeguard(), root, _blind, _copy).verdict == "survived"
    assert trial(_safeguard(proof=""), root, _killing, _copy).verdict == "proof_missing"
    broken = _safeguard(anchor="absent\n")
    assert trial(broken, root, _killing, _copy).verdict == "mutation_invalid"


def test_ignored_files_are_never_copied(tmp_path: Path) -> None:
    """The copy is what a commit could contain: tracked and new files, never ignored ones."""
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "kept.py").write_text("x = 1\n", encoding="utf-8")
    (root / "new_proof.py").write_text("y = 2\n", encoding="utf-8")
    (root / ".gitignore").write_text("scratch.log\n", encoding="utf-8")
    (root / "scratch.log").write_text("noise\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "pkg/kept.py"], cwd=root, check=True)
    copied = tmp_path / "copy"
    copy_committable(root, copied)
    assert (copied / "pkg" / "kept.py").read_text(encoding="utf-8") == "x = 1\n"
    assert (copied / "new_proof.py").read_text(encoding="utf-8") == "y = 2\n"
    assert not (copied / "scratch.log").exists()
