# tests/test_source_apply.py
"""source:apply: source is created and edited from a declarative spec, all or nothing (D.25).

Every edit in this repository was a program written into a terminal, each with its own
anchor counts, line rules and write. A spec is data: a fixed task validates it, judges it by
policy, and applies it all or nothing, so no edit logic is invented at execution time again.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import spine
from source_apply import ENTRYPOINT, POLICY, ApplyRequest, main


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text, encoding="utf-8")
    return repo


def _op(op: str, path: str, **fields: str) -> str:
    lines = ["[[operations]]", f'op = "{op}"', f'path = "{path}"']
    lines += [f"{key} = {json.dumps(value)}" for key, value in fields.items()]
    return "\n".join(lines) + "\n"


def _spec(*ops: str) -> str:
    return 'contract = "source-apply/v1"\n\n' + "\n".join(ops)


def _apply(tmp_path: Path, repo: Path, *ops: str) -> int:
    spec = tmp_path / "spec.toml"
    spec.write_text(_spec(*ops), encoding="utf-8")
    return main([str(spec)], root=repo)


def _message(capsys: pytest.CaptureFixture[str]) -> str:
    return str(json.loads(capsys.readouterr().out)["message"])


def test_a_spec_with_one_failing_file_writes_nothing(tmp_path: Path) -> None:
    """All or nothing: the create is valid, the replace is not, so neither file changes."""
    repo = _repo(tmp_path, {"pkg/old.py": "z = 2\n"})
    created = _op("create", "pkg/new.py", content="x = 1\n")
    broken = _op("replace", "pkg/old.py", anchor="absent", replacement="y = 3")
    assert _apply(tmp_path, repo, created, broken) == 2
    assert not (repo / "pkg" / "new.py").exists()
    assert (repo / "pkg" / "old.py").read_text(encoding="utf-8") == "z = 2\n"


def test_a_create_and_a_replace_apply_and_read_back(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"pkg/old.py": "z = 2\n"})
    created = _op("create", "pkg/new.py", content="x = 1\n")
    replaced = _op("replace", "pkg/old.py", anchor="z = 2", replacement="z = 3")
    assert _apply(tmp_path, repo, created, replaced) == 0
    assert (repo / "pkg" / "new.py").read_text(encoding="utf-8") == "x = 1\n"
    assert (repo / "pkg" / "old.py").read_text(encoding="utf-8") == "z = 3\n"


def test_a_path_outside_the_repository_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path, {})
    assert _apply(tmp_path, repo, _op("create", "../escape.py", content="x = 1\n")) == 2
    assert not (tmp_path / "escape.py").exists()
    assert "ERR_SOURCE_APPLY_PATH_OUTSIDE" in _message(capsys)


def test_an_anchor_found_twice_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path, {"pkg/old.py": "z = 2\nz = 2\n"})
    twice = _op("replace", "pkg/old.py", anchor="z = 2", replacement="z = 3")
    assert _apply(tmp_path, repo, twice) == 2
    assert "ERR_SOURCE_APPLY_ANCHOR_COUNT" in _message(capsys)
    assert (repo / "pkg" / "old.py").read_text(encoding="utf-8") == "z = 2\nz = 2\n"


def test_a_python_file_left_unparseable_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path, {})
    assert _apply(tmp_path, repo, _op("create", "pkg/bad.py", content="def (\n")) == 2
    assert "ERR_SOURCE_APPLY_PYTHON_UNPARSEABLE" in _message(capsys)


def test_a_written_python_line_over_100_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """M28, now policy: a line a spec writes into Python stays within 100."""
    repo = _repo(tmp_path, {})
    long = "x = " + "1" * 100 + "\n"
    assert _apply(tmp_path, repo, _op("create", "pkg/long.py", content=long)) == 2
    assert "ERR_SOURCE_APPLY_LINE_TOO_LONG" in _message(capsys)


def test_an_absent_request_is_refused_by_the_policy() -> None:
    found = spine.evaluate(ApplyRequest(operations=()), "not_source_apply", POLICY, ENTRYPOINT)
    codes = [rule.code for rule in found.rules if rule.outcome == "fail"]
    assert "ERR_SOURCE_APPLY_INPUT_MISSING" in codes, found


def test_a_spec_read_from_stdin_applies(tmp_path: Path) -> None:
    """A spec reaches the repository as data piped into a fixed task, never as a program."""
    repo = _repo(tmp_path, {})
    spec = io.StringIO(_spec(_op("create", "pkg/new.py", content="x = 1\n")))
    assert main(["-"], root=repo, stdin=spec) == 0
    assert (repo / "pkg" / "new.py").read_text(encoding="utf-8") == "x = 1\n"


def test_the_claim_names_the_repository_parsed_from_origin() -> None:
    """recsys declares no project identity: git's origin names the repository (A.13).

    Every GitHub form of the remote gives the one https URL a claim records, whatever transport
    is configured; a remote that is not GitHub is refused rather than recorded.
    """
    from source_apply import _github_url

    for remote in (
        "git@github.com:o/r.git",
        "ssh://git@github.com/o/r",
        "https://github.com/o/r.git\n",
    ):
        assert _github_url(remote) == "https://github.com/o/r"
    with pytest.raises(ValueError):
        _github_url("https://gitlab.com/o/r")
