# tests/test_centralization_record.py
"""Every capability the recorded cscie103 lacks is classified, checked offline (A.277).

cscie103 is private: CI's token reads only this repository, and the snapshot gate turns global git
config off by design, so no gate can read cscie103 live. centralization:record writes its
capabilities as data; this proof reads files alone, and a stale record only makes it stricter.
"""

from __future__ import annotations

import pytest

import centralization
from nonvacuous import nonempty

RECORD = centralization.ROOT / "contracts" / "centralization-upstream.toml"


def test_every_capability_the_recorded_upstream_lacks_is_classified() -> None:
    assert RECORD.exists(), "no recorded upstream: run centralization:record"
    recorded = frozenset(nonempty(centralization.recorded(RECORD)))
    listed = tuple(sorted(centralization.capabilities(centralization.ROOT) - recorded))
    try:
        centralization.judge(listed, centralization.REGISTER)
    except SystemExit as refused:
        pytest.fail(str(refused))
