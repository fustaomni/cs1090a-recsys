"""develop requires the quality gate from GitHub Actions, kept as a ruleset in code (A.105).

GitHub reports a running check that no rule requires as UNSTABLE, which merge.readiness refuses,
and a required one as BLOCKED, which it waits on. The ruleset is kept in the REST API's own shape
under .github/rulesets, so a rule change is a reviewed diff. Its one required context is pinned
to the GitHub Actions app (integration_id 15368) and must be the job name ci.yml reports.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GITHUB_ACTIONS = 15368


def test_develop_requires_the_quality_gate_from_github_actions() -> None:
    path = ROOT / ".github" / "rulesets" / "develop.json"
    assert path.is_file(), "develop's ruleset is not kept as code"
    ruleset = json.loads(path.read_text(encoding="utf-8"))
    assert ruleset["target"] == "branch" and ruleset["enforcement"] == "active", ruleset
    assert ruleset["conditions"]["ref_name"]["include"] == ["refs/heads/develop"], ruleset
    rules = [rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks"]
    assert len(rules) == 1, ruleset["rules"]
    checks = rules[0]["parameters"]["required_status_checks"]
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    gate = yaml.safe_load(ci.read_text(encoding="utf-8"))["jobs"]["check"]["name"]
    assert checks == [{"context": gate, "integration_id": GITHUB_ACTIONS}], (checks, gate)
