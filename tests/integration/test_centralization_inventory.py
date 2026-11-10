# tests/integration/test_centralization_inventory.py
"""Every capability cscie103 lacks at its develop tip is classified (A.277).

centralization:inventory resolves cscie103's develop over the network, so no offline gate ran it
and four capabilities landed unclassified. This proof is that inventory in the integration tier,
which CI runs with network: an unclassified capability fails here, named.
"""

from __future__ import annotations

import tomllib

import pytest

import centralization
import upstream

pytestmark = pytest.mark.integration


def test_every_capability_cscie103_lacks_is_classified() -> None:
    provenance = tomllib.loads(centralization.PROVENANCE.read_text(encoding="utf-8"))
    source = provenance["source"]
    theirs = upstream.checkout(source, upstream.tip(source, centralization.BRANCH))
    listed = centralization.absent(centralization.ROOT, theirs)
    try:
        centralization.judge(listed, centralization.REGISTER)
    except SystemExit as refused:
        pytest.fail(str(refused))
