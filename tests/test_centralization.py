"""What this repository has that cscie103 lacks is listed and classified (A.205).

A capability born in a sibling must reach cscie103, the repository every sibling and every
generated project ports from, so first it has to be seen. A capability is a mise task or a
script; one present here and absent from cscie103's checkout at its resolved develop tip is
listed by its kind, and contracts/centralization.toml must classify each listed one as generic
or project-specific, with its reason. An unclassified one is refused by its id.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _inventory() -> ModuleType:
    found = importlib.util.find_spec("centralization")
    assert found is not None, "no centralization inventory lists what cscie103 lacks yet"
    return importlib.import_module("centralization")


def _checkout(root: Path, scripts: tuple[str, ...], tasks: tuple[str, ...]) -> Path:
    """A checkout holding these scripts under scripts/ and these tasks in mise.toml."""
    (root / "scripts").mkdir(parents=True)
    for name in scripts:
        (root / "scripts" / name).write_text("x = 1\n", encoding="utf-8")
    blocks = [f'[tasks."{task}"]\nrun = "true"\n' for task in tasks]
    (root / "mise.toml").write_text("\n".join(blocks), encoding="utf-8")
    return root


def _pair(tmp_path: Path) -> tuple[Path, Path]:
    """This repository with one script and one task of its own; cscie103 with only the shared."""
    ours = _checkout(tmp_path / "ours", ("shared.py", "born_here.py"), ("shared", "born:here"))
    theirs = _checkout(tmp_path / "theirs", ("shared.py",), ("shared",))
    return ours, theirs


def test_a_capability_absent_from_the_source_is_listed(tmp_path: Path) -> None:
    """A script and a task only this repository has are both listed, each by its kind."""
    inventory = _inventory()
    ours, theirs = _pair(tmp_path)
    listed = inventory.absent(ours, theirs)
    assert listed == ("script:scripts/born_here.py", "task:born:here"), listed


def test_a_capability_present_in_the_source_is_not_listed(tmp_path: Path) -> None:
    """What cscie103 already has is never listed, whether a script or a task."""
    inventory = _inventory()
    ours, theirs = _pair(tmp_path)
    listed = inventory.absent(ours, theirs)
    assert "script:scripts/shared.py" not in listed, listed
    assert "task:shared" not in listed, listed


def test_an_unclassified_absent_capability_is_refused(tmp_path: Path) -> None:
    """Only the task is classified, so the script born here is refused by its id."""
    inventory = _inventory()
    register = tmp_path / "centralization.toml"
    register.write_text(
        'contract = "centralization/v1"\n\n[[capabilities]]\nid = "task:born:here"\n'
        'class = "generic"\nreason = "a family capability"\n',
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as refused:
        inventory.judge(("script:scripts/born_here.py", "task:born:here"), register)
    assert "script:scripts/born_here.py" in str(refused.value), refused.value
    assert "task:born:here" not in str(refused.value), refused.value
