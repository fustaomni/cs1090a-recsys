"""centralization:inventory -- what this repository has that cscie103 lacks, classified (A.205).

A capability born in a sibling reaches cscie103, the repository every sibling and every
generated project ports from. A capability is a mise task or a script. cscie103 is read at the
commit its develop resolves to (A.204), checked out from trees alone (A.113), and every
capability here that it lacks must be classified in contracts/centralization.toml as generic,
to be centralized, or project-specific, each with its reason. An unclassified one is refused
by its id, so nothing born here is forgotten.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import upstream

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "contracts" / "centralization.toml"
PROVENANCE = ROOT / "contracts" / "provenance.toml"
BRANCH = "develop"
CLASSES = ("generic", "project")


def capabilities(root: Path) -> frozenset[str]:
    """A checkout's tasks and scripts, as task:<name> and script:scripts/<file>.py."""
    config = tomllib.loads((root / "mise.toml").read_text(encoding="utf-8"))
    tasks = {f"task:{name}" for name in config.get("tasks", {})}
    scripts = {f"script:scripts/{path.name}" for path in (root / "scripts").glob("*.py")}
    return frozenset(tasks | scripts)


def absent(ours: Path, theirs: Path) -> tuple[str, ...]:
    """Every capability ours has and theirs lacks, sorted."""
    return tuple(sorted(capabilities(ours) - capabilities(theirs)))


def judge(listed: tuple[str, ...], register: Path) -> None:
    """Refuse, naming each, every listed capability the register does not classify."""
    text = register.read_text(encoding="utf-8") if register.exists() else ""
    entries = tomllib.loads(text).get("capabilities", [])
    classified = {
        entry["id"] for entry in entries if entry.get("class") in CLASSES and entry.get("reason")
    }
    unclassified = [item for item in listed if item not in classified]
    if unclassified:
        named = ", ".join(unclassified)
        raise SystemExit(f"not classified in contracts/centralization.toml: {named}")


def main() -> int:
    """List what cscie103 lacks at its resolved develop tip, then judge the classification."""
    source = tomllib.loads(PROVENANCE.read_text(encoding="utf-8"))["source"]
    commit = upstream.tip(source, BRANCH)
    theirs = upstream.checkout(source, commit)
    listed = absent(ROOT, theirs)
    print(f"{source} {BRANCH} resolved to {commit}; {len(listed)} capabilities it lacks:")
    for item in listed:
        print(f"  {item}")
    judge(listed, REGISTER)
    print("every one is classified in contracts/centralization.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
