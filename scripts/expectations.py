"""Every kind of expectation the plan declares has its runtime record type and producer (A.65).

A plan step is done when its done_when items hold. Each item has a kind, and plan:status observes
it from the ref: a path in the tree, a task in mise.toml, a test function defined in a file. That
is coverage, not verification: a test can be defined and still red. contracts/expectations.toml
names, for each kind the plan uses, the runtime record that shows the expectation held and the
task that produces it. The producer must be a registered capability that emits the record, or
emits command-outcome/v1 and carries it, naming it in its implementation; a kind the plan uses
with no such entry is refused.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import Field

from capabilities import ENVELOPE, Capabilities
from contract_base import Contract, from_document

ROOT = Path(__file__).resolve().parent.parent
REGISTER = Path("contracts") / "expectations.toml"
PLAN = Path("context") / "plan.toml"
Kind = Literal["path", "task", "release", "pr", "proof"]


class Expectation(Contract):
    """One evidence kind: the record that shows it held at run time, and its producer."""

    kind: Kind
    record: str = Field(pattern=r"^[a-z][a-z-]*/v[0-9]+$")
    producer: str = Field(min_length=1)


class Expectations(Contract):
    """expectations/v1: each evidence kind the plan uses, with its record and producer."""

    contract: Literal["expectations/v1"] = "expectations/v1"
    expectations: tuple[Expectation, ...]


def load(root: Path = ROOT) -> Expectations:
    """The register, validated."""
    text = (root / REGISTER).read_text(encoding="utf-8")
    return from_document(Expectations, tomllib.loads(text))


def used_kinds(root: Path = ROOT) -> set[str]:
    """Every evidence kind any plan step's done_when names."""
    plan = tomllib.loads((root / PLAN).read_text(encoding="utf-8"))
    return {item["kind"] for step in plan.get("steps", []) for item in step.get("done_when", [])}


def _carries(expectation: Expectation, capabilities: Capabilities, root: Path) -> str | None:
    entries = [entry for entry in capabilities.capabilities if entry.task == expectation.producer]
    if not entries:
        return f"{expectation.kind}: {expectation.producer} is not a registered capability"
    entry = entries[0]
    if entry.emits == expectation.record:
        return None
    source = (root / entry.implementation).read_text(encoding="utf-8")
    if entry.emits == ENVELOPE and expectation.record in source:
        return None
    return f"{expectation.kind}: {expectation.producer} does not produce {expectation.record}"


def findings(
    register: Expectations, used: Iterable[str], capabilities: Capabilities, root: Path
) -> list[str]:
    """Each kind used with no record, each kind paired twice, and each producer that is not one."""
    named = [expectation.kind for expectation in register.expectations]
    missing = sorted(set(used) - set(named))
    found = [f"{kind}: used by the plan with no record type" for kind in missing]
    found += [f"{kind}: paired {n} times" for kind, n in sorted(Counter(named).items()) if n > 1]
    problems = (_carries(item, capabilities, root) for item in register.expectations)
    found += [problem for problem in problems if problem is not None]
    return found
