# scripts/plan_proofs.py
"""Every planned step declares a proof; the proof-less past is a baseline that only shrinks (D.266).

PORTED FROM cs1090a-recsys's plan:audit (RS.13). recsys found thirty-eight steps that claimed to
refuse something and were proved only by inspection: a file existing, a task declared, a pull
request merged. Each shows an artefact; none shows that a rule refuses anything. This hub already
reads a named proof as a test function its file really defines (plan_status.defined_tests); what
it lacked is the rule that every step names one.

A BASELINE THAT ONLY SHRINKS. Steps planned before the rule sit in
context/plan-proof-baseline.toml. No id joins it that origin/develop's baseline did not hold, and
none stays once its step declares a proof, so it can only fall until it is empty. plan:add,
plan:amend and plan:trace each refuse what would break that. A generated project's own plan
starts with every step proven, so it needs no baseline at all.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal

from contract_base import Contract, from_document
from gitenv import git
from plan_models import ProjectPlan

BASELINE = Path("context") / "plan-proof-baseline.toml"
UPSTREAM = "origin/develop"
HEADER = (
    "# context/plan-proof-baseline.toml",
    "# Steps planned before every step had to declare a proof (D.266, proof-baseline/v1). It only",
    "# shrinks: plan:trace refuses an id origin/develop's baseline did not hold, and an id whose",
    "# step now declares a proof. Prove a step, then remove its id here in the same change.",
)


class ProofBaseline(Contract):
    """proof-baseline/v1: the steps planned before every step had to declare a proof."""

    contract: Literal["proof-baseline/v1"] = "proof-baseline/v1"
    steps: tuple[str, ...]


def declares_proof(done_when: object) -> bool:
    """Whether a done_when, from a spec or a plan file, names at least one proof."""
    if not isinstance(done_when, list):
        return False
    return any(isinstance(item, Mapping) and item.get("kind") == "proof" for item in done_when)


def _order(step: str) -> tuple[str, int]:
    thread, _, number = step.partition(".")
    return thread, int(number) if number.isdigit() else 0


def baseline_text(steps: Iterable[str]) -> str:
    """The baseline file, its ids in plan order."""
    ordered = sorted(set(steps), key=_order)
    listed = ["steps = ["] + [f'  "{step}",' for step in ordered] + ["]"]
    body = listed if ordered else ["steps = []"]
    return "\n".join([*HEADER, 'contract = "proof-baseline/v1"', *body, ""])


def _parsed(text: str) -> frozenset[str]:
    return frozenset(from_document(ProofBaseline, tomllib.loads(text)).steps)


def read_baseline(root: Path) -> frozenset[str]:
    """The committed baseline; none at all where a project never needed one."""
    path = root / BASELINE
    if not path.is_file():
        return frozenset()
    return _parsed(path.read_text(encoding="utf-8"))


def previous_baseline(root: Path) -> frozenset[str] | None:
    """The baseline where this branch left origin/develop, or None with none to compare with.

    THE MERGE-BASE, NOT THE TIP (D.499), as D.269 reads the problem registry. Read at the
    tip, every entry develop removed after the fork looked added here, so a checkout behind
    develop was refused for D.120 and D.163, which it never touched. No merge-base, from a
    missing ref or unrelated history, or no baseline there, leaves nothing to compare.
    """
    fork = git("merge-base", "HEAD", UPSTREAM, cwd=root)
    if fork.returncode != 0:
        return None
    shown = git("show", f"{fork.stdout.strip()}:{BASELINE.as_posix()}", cwd=root)
    if shown.returncode != 0:
        return None
    return _parsed(shown.stdout)


def proof_gaps(
    plan: ProjectPlan, baseline: frozenset[str], previous: frozenset[str] | None
) -> list[str]:
    """Every way the plan and its baseline break the rule, named."""
    gaps: list[str] = []
    proven = {step.id: any(item.kind == "proof" for item in step.done_when) for step in plan.steps}
    for step in plan.steps:
        if not proven[step.id] and step.id not in baseline:
            gaps.append(f"{step.id} declares no proof in done_when")
    for entry in sorted(baseline, key=_order):
        if entry not in proven:
            gaps.append(f"{entry} is in the proof baseline but is not a step")
        elif proven[entry]:
            gaps.append(f"{entry} declares a proof, so it leaves the proof baseline")
    if previous is not None:
        for entry in sorted(baseline - previous, key=_order):
            gaps.append(f"{entry} joined the proof baseline, which only shrinks")
    return gaps
