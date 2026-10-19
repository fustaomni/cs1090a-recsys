# tests/test_monkeypatch_raising.py
"""A proof patches an attribute that exists with pytest's default raising (A.133).

monkeypatch.setattr raises AttributeError when the attribute is missing, unless raising=False.
That flag is right only while the patched name does not exist yet, between RED and GREEN; once
it exists, the flag only hides a rename, and a proof asserting that nothing was called passes
with nothing called. This reads every proof's syntax tree, so the rule holds as tests are added.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path

from nonvacuous import nonempty

TESTS = Path(__file__).resolve().parent


def _flagged(source: str) -> list[tuple[str, str, int]]:
    """Each monkeypatch.setattr(<module>, "<name>", ..., raising=False): module, name, line."""
    found: list[tuple[str, str, int]] = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "setattr" or len(node.args) < 2:
            continue
        flag = next((k.value for k in node.keywords if k.arg == "raising"), None)
        target, name = node.args[0], node.args[1]
        # IN THE CONDITION ITSELF: mypy narrows only there, never through an aliased boolean.
        if (
            isinstance(flag, ast.Constant)
            and flag.value is False
            and isinstance(name, ast.Constant)
            and isinstance(name.value, str)
            and isinstance(target, ast.Name)
        ):
            found.append((target.id, name.value, node.lineno))
    return found


def _stale(source: str) -> list[str]:
    """The flagged patches whose module already has the name: the flag can only hide a rename."""
    stale: list[str] = []
    for module, name, line in _flagged(source):
        if importlib.util.find_spec(module) is None:
            continue
        if hasattr(importlib.import_module(module), name):
            stale.append(f"line {line}: {module}.{name}")
    return stale


def test_no_proof_patches_an_existing_attribute_with_raising_false() -> None:
    stale = {
        path.name: found
        for path in nonempty(sorted(TESTS.glob("test_*.py")))
        if (found := _stale(path.read_text(encoding="utf-8")))
    }
    assert stale == {}, stale


def test_the_rule_flags_a_patch_whose_name_exists_and_spares_one_that_does_not() -> None:
    """The guard bites: A.122's old line is flagged, and a name not yet written is spared."""
    old = 'monkeypatch.setattr(worktree, "_trust", retrust, raising=False)\n'
    new = 'monkeypatch.setattr(worktree, "_not_written_yet", retrust, raising=False)\n'
    assert _stale(old) == ["line 1: worktree._trust"]
    assert _stale(new) == []
