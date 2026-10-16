"""A policy set is admitted only by its manifest: files, digests, roots, check and tests (A.30)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from policy_admission import POLICIES, ROOT, Domain, Manifest, PolicyFile, findings, load

POLICY = "package probe\n\nallow if input.ok\n"
PASSING = 'package probe_test\n\ntest_allow if data.probe.allow with input as {"ok": true}\n'
FAILING = 'package probe_test\n\ntest_allow if data.probe.allow with input as {"ok": false}\n'


def _set(tmp_path: Path, test: str | None = PASSING) -> Path:
    folder = tmp_path / "probe"
    folder.mkdir()
    (folder / "probe.rego").write_text(POLICY, encoding="utf-8")
    if test is not None:
        (folder / "probe_test.rego").write_text(test, encoding="utf-8")
    return folder


def _domain(folder: Path) -> Domain:
    files = tuple(
        PolicyFile(name=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(folder.glob("*.rego"))
        if not path.name.endswith("_test.rego")
    )
    return Domain(name="probe", root="probe", files=files, test="probe_test.rego")


def test_a_policy_set_missing_its_test_file_is_refused(tmp_path: Path) -> None:
    folder = _set(tmp_path, test=None)
    found = findings(Manifest(domains=(_domain(folder),)), tmp_path)
    assert "probe: its test file probe_test.rego is missing" in found


def test_a_file_outside_the_manifest_is_refused(tmp_path: Path) -> None:
    folder = _set(tmp_path)
    manifest = Manifest(domains=(_domain(folder),))
    (folder / "extra.rego").write_text("package probe\n\nextra := 1\n", encoding="utf-8")
    assert "probe: extra.rego is outside the manifest" in findings(manifest, tmp_path)


def test_a_policy_whose_tests_fail_is_not_admitted(tmp_path: Path) -> None:
    folder = _set(tmp_path, test=FAILING)
    found = findings(Manifest(domains=(_domain(folder),)), tmp_path)
    assert found == ["probe: its tests failed or ran nothing"]


def test_one_domain_present_and_one_missing_is_refused(tmp_path: Path) -> None:
    present = _domain(_set(tmp_path))
    assert findings(Manifest(domains=(present,)), tmp_path) == []
    absent = Domain(name="absent", root="absent", files=(), test="absent_test.rego")
    both = Manifest(domains=(present, absent))
    assert findings(both, tmp_path) == ["absent: declared but missing"]


def test_the_repositorys_manifest_is_admitted() -> None:
    assert findings(load(ROOT), POLICIES) == []
