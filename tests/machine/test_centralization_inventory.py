# tests/machine/test_centralization_inventory.py
"""Every capability cscie103 lacks at its develop tip is classified (A.277).

centralization:inventory resolves cscie103's develop over the network, so no offline gate ran it
and four capabilities landed unclassified. cscie103 is private and CI's GITHUB_TOKEN is scoped to
this repository alone, so the proof is in the machine tier: every developer gate runs it with the
developer's own credentials, pr's snapshot gate included, and CI's runner never does.
"""

from __future__ import annotations

import tomllib

import pytest

import centralization
import upstream

pytestmark = pytest.mark.machine


def test_every_capability_cscie103_lacks_is_classified() -> None:
    provenance = tomllib.loads(centralization.PROVENANCE.read_text(encoding="utf-8"))
    source = provenance["source"]
    theirs = upstream.checkout(source, upstream.tip(source, centralization.BRANCH))
    listed = centralization.absent(centralization.ROOT, theirs)
    try:
        centralization.judge(listed, centralization.REGISTER)
    except SystemExit as refused:
        pytest.fail(str(refused))
