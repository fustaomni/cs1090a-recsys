# tests/test_tools_verify.py
"""Each publisher's verification method, driven offline with a key and a report made here (A.279).

tools:verify runs these methods against real releases. This proof drives each one with a signing
key generated in the test, a tampered copy, and a recorded npm audit report, touching no network.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from types import ModuleType

from pysequoia import SignatureMode, Tsk, sign

ASSET = "node-v24.21.0-linux-x64.tar.gz"
DIGEST = "6e1db87ef58b8819e5d5402eff1536491b18edd8eb7bee5ef7897876e88dc5ff"


def _module() -> ModuleType:
    assert importlib.util.find_spec("tools_verify") is not None, "tools_verify is not written yet"
    return importlib.import_module("tools_verify")


def test_each_publisher_kind_is_verified_by_its_own_method() -> None:
    tools_verify = _module()
    key = Tsk.generate("release <release@example.invalid>")
    cert = key.extract_certificate()
    shasums = f"{DIGEST}  {ASSET}\n".encode()
    signature = sign(key.signer(), shasums, mode=SignatureMode.DETACHED, armor=False)
    # NODE: the release key's signature verifies, and the signed digest is the asset's.
    assert tools_verify.node_signer(shasums, signature, [cert]) == cert.fingerprint
    assert tools_verify.signed_sha256(shasums, ASSET) == DIGEST
    tampered = shasums.replace(b"6e1d", b"0000")
    assert tools_verify.node_signer(tampered, signature, [cert]) == ""
    # NPM: the audit verified this exact package's registry signature and attestation.
    verified = [{"name": "npm", "version": "12.2.0", "attestations": {"url": "recorded"}}]
    report = {"invalid": [], "missing": [], "verified": verified}
    assert tools_verify.npm_audited(json.dumps(report), "npm", "12.2.0")
    assert not tools_verify.npm_audited(json.dumps(report), "npm", "12.2.2")
    refused = {**report, "invalid": [{"name": "npm", "version": "12.2.0"}]}
    assert not tools_verify.npm_audited(json.dumps(refused), "npm", "12.2.0")
    # GITHUB: the release asset a lock URL names is the one gh release verify-asset checks.
    url = (
        "https://github.com/open-policy-agent/opa/releases/download/v1.21.1/opa_linux_amd64_static"
    )
    named = ("open-policy-agent/opa", "v1.21.1", "opa_linux_amd64_static")
    assert tools_verify.github_asset(url) == named
