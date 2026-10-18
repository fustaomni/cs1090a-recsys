"""One contract per concept: each contract id has one model, and decisions are decision/v1 (A.71).

A contract id is declared by a model's `contract: Literal[...]` field. Two models declaring one id
would be two shapes answering to one name, so every id must have exactly one declaring class, and
a class's CONTRACT_ID, where it has one, must be its own contract. A decision is decision/v1, the
spine's Decision: every field or parameter named decision must be annotated with it, imported from
spine, never a same-named class from elsewhere. Both are read by parsing scripts/, never by
matching text, so a name alone can neither satisfy nor evade them.

A POLICY'S OWN ANSWER IS LISTED, NEVER INFERRED (A.19). merge.readiness decides wait, merge or
refuse, and pr.Readiness carries it under the policy's name. An exception names one path, class
and field, and one that matches nothing is stale, so none outlives the code it excused.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = "spine"
Source = tuple[str, str]
EXCEPTIONS: dict[str, str] = {
    "scripts/pr.py::Readiness.decision": "merge.readiness's own decision: wait, merge or refuse",
}


def sources(root: Path = ROOT) -> list[Source]:
    """Every module under scripts/, as its repository path and its text."""
    paths = sorted((root / "scripts").glob("*.py"))
    return [(path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")) for path in paths]


def _literal_ids(annotation: ast.expr) -> list[str]:
    if not (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)):
        return []
    if annotation.value.id != "Literal":
        return []
    inner = annotation.slice
    items = inner.elts if isinstance(inner, ast.Tuple) else [inner]
    return [str(item.value) for item in items if isinstance(item, ast.Constant)]


def _fields(node: ast.ClassDef) -> dict[str, ast.AnnAssign]:
    return {
        stmt.target.id: stmt
        for stmt in node.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }


def contract_findings(modules: Iterable[Source]) -> list[str]:
    """Every contract id declared by more than one model, and every CONTRACT_ID that drifted."""
    owners: dict[str, list[str]] = defaultdict(list)
    drifted: list[str] = []
    for path, text in modules:
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.ClassDef):
                continue
            name = f"{path}::{node.name}"
            fields = _fields(node)
            ids = _literal_ids(fields["contract"].annotation) if "contract" in fields else []
            for contract_id in ids:
                owners[contract_id].append(name)
            declared = fields.get("CONTRACT_ID")
            value = declared.value if declared is not None else None
            constant = value.value if isinstance(value, ast.Constant) else None
            if isinstance(constant, str) and constant not in ids:
                drifted.append(f"{name}: CONTRACT_ID {constant} is not its contract")
    shared = [
        f"{contract_id}: declared by {', '.join(sorted(names))}"
        for contract_id, names in sorted(owners.items())
        if len(names) > 1
    ]
    return shared + drifted


def _decision_names(module: ast.Module, path: str) -> set[str]:
    names: set[str] = {"Decision"} if Path(path).stem == HOME else set()
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module == HOME:
            for alias in node.names:
                if alias.name == "Decision":
                    names.add(alias.asname or alias.name)
    return names


def _is_none(annotation: ast.expr) -> bool:
    return isinstance(annotation, ast.Constant) and annotation.value is None


def _is_decision(annotation: ast.expr | None, names: set[str]) -> bool:
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        held = [part for part in (annotation.left, annotation.right) if not _is_none(part)]
        return bool(held) and all(_is_decision(part, names) for part in held)
    if isinstance(annotation, ast.Name):
        return annotation.id in names
    if isinstance(annotation, ast.Attribute) and isinstance(annotation.value, ast.Name):
        return (annotation.value.id, annotation.attr) == (HOME, "Decision")
    return False


def _owners(module: ast.Module) -> dict[int, str]:
    """Each annotated field's class, by node identity, so an exception names exactly one field."""
    return {
        id(stmt): node.name
        for node in ast.walk(module)
        if isinstance(node, ast.ClassDef)
        for stmt in node.body
        if isinstance(stmt, ast.AnnAssign)
    }


def _scan(modules: Iterable[Source]) -> tuple[list[str], set[str]]:
    """The unlisted decisions that are not decision/v1, and the listed exceptions that matched."""
    found: list[str] = []
    used: set[str] = set()
    for path, text in modules:
        module = ast.parse(text)
        names = _decision_names(module, path)
        owners = _owners(module)
        for node in ast.walk(module):
            annotation: ast.expr | None
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                carrier, annotation = node.target.id == "decision", node.annotation
            elif isinstance(node, ast.arg):
                carrier, annotation = node.arg == "decision", node.annotation
            else:
                continue
            if not carrier or _is_decision(annotation, names):
                continue
            listed = f"{path}::{owners.get(id(node), '')}.decision"
            if listed in EXCEPTIONS:
                used.add(listed)
            else:
                found.append(f"{path}:{node.lineno}: decision is not decision/v1")
    return found, used


def decision_findings(modules: Iterable[Source]) -> list[str]:
    """Every field or parameter named decision not annotated decision/v1, unless listed."""
    return _scan(modules)[0]


def stale_exceptions(modules: Iterable[Source]) -> list[str]:
    """Every listed exception that matches no field: none outlives the code it excused."""
    return sorted(set(EXCEPTIONS) - _scan(modules)[1])
