# scripts/reproduce.py
"""Reproducibility is tested automatically (A.287).

A recorded offline run is re-run from its evidence record alone: the record names its data
snapshot, seeds, protocol and commit, and the re-run receives nothing else. Before anything
re-runs, the data snapshot in hand must equal the recorded one digest for digest; a changed
snapshot is refused by the field that changed. Each recorded metric must then be matched by
the re-run within the declared tolerance, and every one that is not is named with its gap.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from evaluation_evidence import DataSnapshot, EvaluationEvidence

Rerun = Callable[[EvaluationEvidence], Mapping[str, float]]


class SnapshotChangedError(ValueError):
    """The data in hand is not the data the recorded run read."""


@dataclass(frozen=True)
class Reproduction:
    """A re-run's outcome: each recorded metric it missed, with its gap."""

    run_id: str
    tolerance: float
    differences: dict[str, float]

    @property
    def reproduced(self) -> bool:
        """Every recorded metric was matched within the tolerance."""
        return not self.differences


def reproduce(
    recorded: EvaluationEvidence, snapshot: DataSnapshot, rerun: Rerun, tolerance: float
) -> Reproduction:
    """Re-run a recorded run from its evidence and compare its metrics within tolerance."""
    if tolerance < 0:
        raise ValueError(f"a tolerance cannot be negative: {tolerance}")
    ours = recorded.data_snapshot.model_dump()
    theirs = snapshot.model_dump()
    changed = sorted(name for name in ours if ours[name] != theirs.get(name))
    if changed:
        named = ", ".join(changed)
        raise SnapshotChangedError(f"the data snapshot differs in {named}; nothing was re-run")
    measured = rerun(recorded)
    differences: dict[str, float] = {}
    for metric in recorded.metrics:
        value = measured.get(metric.name)
        gap = float("inf") if value is None else abs(value - metric.value)
        if gap > tolerance:
            differences[metric.name] = gap
    return Reproduction(recorded.run_id, tolerance, differences)
