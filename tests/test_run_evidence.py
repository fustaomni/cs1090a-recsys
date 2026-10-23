"""Every run keeps both its streams as evidence, each in a path no other run shares (A.41)."""

from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from nonvacuous import nonempty
from run_task import main

TASK = "probe"
SPEAKS = "import sys; print('out'); print('err', file=sys.stderr)"


def _run(tmp_path: Path, name: str) -> int:
    return main(
        [TASK],
        ledger=tmp_path / f"{name}.jsonl",
        evidence=tmp_path / "evidence",
        launcher=(sys.executable, "-c", SPEAKS),
        declared=frozenset({TASK}),
        read_only=frozenset({TASK}),
        signer=None,
    )


def test_two_concurrent_runs_never_share_an_evidence_path(tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda name: _run(tmp_path, name), ["first", "second"]))
    assert codes == [0, 0]
    folders = sorted((tmp_path / "evidence").iterdir())
    assert len(folders) == 2
    assert all((folder / "stdout").is_file() for folder in nonempty(folders))
    assert all((folder / "stderr").is_file() for folder in nonempty(folders))


def test_both_streams_are_retained_with_their_digests(tmp_path: Path) -> None:
    assert _run(tmp_path, "solo") == 0
    (folder,) = (tmp_path / "evidence").iterdir()
    manifest = json.loads((folder / "evidence.json").read_text(encoding="utf-8"))
    for stream, text in (("stdout", "out\n"), ("stderr", "err\n")):
        kept = (folder / stream).read_bytes()
        assert kept == text.encode("utf-8")
        assert manifest[f"{stream}_sha256"] == hashlib.sha256(kept).hexdigest()
