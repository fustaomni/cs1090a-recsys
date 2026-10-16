"""Every test declares its level by where it lives; an unclassified test is refused (A.39).

A level is a lane of the gate: unit tests are hermetic and run on every push, acceptance tests
drive the real gateway in a sandbox, integration tests need the network and run apart. Each test
directory names its level in contracts/test-levels.toml, and a test takes the level of the
deepest directory that names one. A test in no named directory, or one whose own marker names
another level, is refused at collection, so nothing runs in the wrong lane or silently in none.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "contracts" / "test-levels.toml"


def declared(path: Path = REGISTER) -> dict[str, str]:
    """Each test directory and the level it declares, from contracts/test-levels.toml."""
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    return {str(name): str(level) for name, level in document["directories"].items()}


def classify(nodeid: str, marked: Iterable[str], declared: Mapping[str, str]) -> str:
    """The level a test takes from its directory, or ValueError naming why it has none."""
    directory = PurePosixPath(nodeid.split("::", 1)[0]).parent
    owners = [
        PurePosixPath(name)
        for name in declared
        if PurePosixPath(name) in (directory, *directory.parents)
    ]
    if not owners:
        raise ValueError(f"{nodeid}: {directory} declares no level")
    owner = max(owners, key=lambda path: len(path.parts))
    level = declared[owner.as_posix()]
    claimed = set(marked) & set(declared.values())
    if claimed - {level}:
        raise ValueError(f"{nodeid}: marked {sorted(claimed)}, but {owner} is {level}")
    return level
