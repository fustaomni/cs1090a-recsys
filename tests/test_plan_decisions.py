# tests/test_plan_decisions.py
"""Milestone 2's steps done outside this repository are retired as decisions (A.327).

Steps bound to FAS OnDemand, or to documents the group prepares outside the repository, cannot
be finished here. plan:retire turns each into a superseded decision that keeps its id and title
and states why, so every commit naming the id still traces to it and nothing is deleted.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from contract_base import from_document
from plan_models import ProjectPlan

PLAN = Path(__file__).resolve().parent.parent / "context" / "plan.toml"
FAS = "FAS OnDemand is closed and development moved to the MacBook Pro"
OUTSIDE = (
    "the group prepares the revised proposal, the slides and the presentation"
    " outside the repository"
)
SUPERSEDED_RUN = (
    "A.329's ms2:execute runs the notebook in a fresh kernel on the MacBook Pro"
    " instead of an OnDemand session"
)
RETIRED = {
    "A.224": FAS,
    "A.226": OUTSIDE,
    "A.227": OUTSIDE,
    "A.237": SUPERSEDED_RUN,
    "A.238": OUTSIDE,
    "A.253": OUTSIDE,
    "A.269": "A.225 supersedes it",
    "A.270": OUTSIDE,
    "A.271": OUTSIDE,
}


def test_the_milestone_2_retirements_are_decisions_with_reasons() -> None:
    plan = from_document(ProjectPlan, tomllib.loads(PLAN.read_text(encoding="utf-8")))
    live = {step.id for step in plan.steps} & RETIRED.keys()
    assert not live, sorted(live)
    decided = {
        decision.id: (decision.state, decision.reason)
        for decision in plan.decisions
        if decision.id in RETIRED
    }
    expected = {step: ("superseded", reason) for step, reason in RETIRED.items()}
    assert decided == expected, decided
