"""capabilities:list -- every task is a discoverable, versioned capability contract (A.44).

A task was a name, a description and a command line. contracts/capabilities.toml now gives each
its version, the file that implements it and the contract it emits. Its effect, read-only or
mutating, is not restated here but joined from contracts/task-effects.toml, the declaration the
gateway enforces. The register and mise.toml must agree both ways, and each entry is checked
against its implementation: a task emitting command-outcome/v1 builds a CommandOutcome, one
emitting another contract names it, and one emitting text builds no envelope at all.
"""

from __future__ import annotations

import sys
import tomllib
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import Field

from contract_base import Contract, from_document
from run_task import declared_tasks, read_only_tasks

ROOT = Path(__file__).resolve().parent.parent
REGISTER = Path("contracts") / "capabilities.toml"
ENVELOPE = "command-outcome/v1"
BUILDS_ENVELOPE = ("CommandOutcome", "announce(")


class Capability(Contract):
    """One task: its version, what implements it, and the contract it emits."""

    task: str = Field(min_length=1)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    implementation: str = Field(min_length=1)
    emits: str = Field(pattern=r"^(text|[a-z][a-z-]*/v[0-9]+)$")


class Capabilities(Contract):
    """capabilities/v1: every task this repository declares, as a capability."""

    contract: Literal["capabilities/v1"] = "capabilities/v1"
    capabilities: tuple[Capability, ...]


class Listed(Capability):
    """A capability with the effect the gateway enforces for its task."""

    effect: Literal["read", "mutate"]


class Listing(Contract):
    """capabilities-listing/v1: the register joined with each task's enforced effect."""

    contract: Literal["capabilities-listing/v1"] = "capabilities-listing/v1"
    capabilities: tuple[Listed, ...]


def load(root: Path = ROOT) -> Capabilities:
    """The register, validated."""
    text = (root / REGISTER).read_text(encoding="utf-8")
    return from_document(Capabilities, tomllib.loads(text))


def _evidenced(entry: Capability, source: str) -> bool:
    builds = any(marker in source for marker in BUILDS_ENVELOPE)
    if entry.emits == "text":
        return not builds
    if entry.emits == ENVELOPE:
        return builds
    return entry.emits in source


def _problem(entry: Capability, root: Path) -> str | None:
    path = root / entry.implementation
    if not path.is_file():
        return f"{entry.task}: {entry.implementation} is not a file"
    if not _evidenced(entry, path.read_text(encoding="utf-8")):
        return f"{entry.task}: {entry.implementation} does not emit {entry.emits}"
    return None


def findings(
    register: Capabilities, declared: Iterable[str], read_only: Iterable[str], root: Path
) -> list[str]:
    """Every way the register disagrees with mise.toml, task-effects or its implementations."""
    tasks = set(declared)
    named = Counter(entry.task for entry in register.capabilities)
    found = [f"{task}: a task with no capability" for task in sorted(tasks - set(named))]
    found += [f"{task}: a capability with no task" for task in sorted(set(named) - tasks)]
    found += [f"{task}: registered {n} times" for task, n in sorted(named.items()) if n > 1]
    problems = (_problem(entry, root) for entry in register.capabilities)
    found += [problem for problem in problems if problem is not None]
    stray = sorted(set(read_only) - tasks)
    found += [f"{task}: read-only but not a declared task" for task in stray]
    return found


def main() -> int:
    register = load()
    reads = read_only_tasks(ROOT)
    found = findings(register, declared_tasks(), reads, ROOT)
    if found:
        raise SystemExit("capabilities refused:\n" + "\n".join(found))
    listed = tuple(
        Listed(**entry.model_dump(), effect="read" if entry.task in reads else "mutate")
        for entry in register.capabilities
    )
    print(Listing(capabilities=listed).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
