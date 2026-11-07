# scripts/plan_conflicts.py
"""plan:resolve -- plan-file conflicts resolved as data during a rebase or a merge (D.129).

Two branches that each add a step append to the end of the same three files, so a merge or a
rebase conflicts in all of them although nothing contradicts. The index holds the common
ancestor, ours and theirs (stages 1, 2 and 3). Starting from ours, every entry theirs added is
appended; an entry changed by one side only takes that side; an id issued on both sides with
different content, or an entry changed on both sides, is refused by name. The three files are
validated together through their contracts before anything is written or staged; concluding
the merge or rebase stays with the caller.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Literal, cast

import tomlkit
from pydantic import JsonValue
from tomlkit import TOMLDocument
from tomlkit.items import AoT, Array, Item, Table

from command_outcome import announce
from contract_base import Contract
from gitenv import git
from nix_remediation import ActionableError
from plan_edit import IDS, PLAN, TRACE, _validated, _value
from rebase_state import Operation, _operation, _unmerged
from spine import decide, enforce, evaluate, halted, reasons, refusal_code

ROOT = Path(__file__).resolve().parent.parent
COMMAND = "plan:resolve"
SUBJECT = "plan_resolve"
POLICY = ROOT / "policies" / "runs" / "plan_resolve"
ENTRYPOINT = "data.runs.plan_resolve.deny"
USAGE = "usage: no arguments; run it while a merge or rebase has stopped on a plan file"
Key = tuple[str, ...]


REMEDY = (
    "resolve the named entry in a commit of its own on one side, then merge again; "
    "or abandon the merge"
)


class PlanConflictError(ActionableError):
    """A plan-file conflict this resolver will not decide; the reason names the entry."""

    code = "ERR_PLAN_CONFLICT_REFUSED"

    def __init__(self, message: str, *, remediation: str = REMEDY, **context: object) -> None:
        super().__init__(message, remediation=remediation, **context)


def _stage(root: Path, number: int, relative: Path) -> TOMLDocument:
    shown = git("show", f":{number}:{relative}", cwd=root)
    return tomlkit.parse(shown.stdout) if shown.returncode == 0 else tomlkit.document()


def _plain(item: object) -> object:
    """A tomlkit item as plain data, so two sides compare by value, not by formatting."""
    return item.unwrap() if isinstance(item, Item) else item


def _item(value: object) -> Item:
    return _value(cast(JsonValue, value))


def _key_of(item: object, fields: Key) -> Key | None:
    plain = _plain(item)
    if not isinstance(plain, dict):
        return None
    return tuple(str(plain.get(field, "")) for field in fields)


def _keyed(items: Iterable[object], fields: Key) -> dict[Key, object]:
    keyed: dict[Key, object] = {}
    for item in items:
        key = _key_of(item, fields)
        if key is not None:
            keyed[key] = item
    return keyed


def _union(
    label: str,
    fields: Key,
    collections: tuple[Iterable[object], Iterable[object], Iterable[object]],
    replace: Callable[[Key, object], None],
    append: Callable[[object], None],
) -> None:
    """Theirs folded into ours by key; a change on both sides is refused by name."""
    base, ours, theirs = (_keyed(items, fields) for items in collections)
    for key, item in theirs.items():
        name = " ".join(key)
        theirs_value = _plain(item)
        before = _plain(base[key]) if key in base else None
        if key in ours:
            ours_value = _plain(ours[key])
            if ours_value == theirs_value or theirs_value == before:
                continue
            if key not in base:
                raise PlanConflictError(f"{label} {name} was issued on both sides")
            if ours_value != before:
                raise PlanConflictError(f"{label} {name} was edited on both sides")
            replace(key, theirs_value)
        elif key in base:
            if theirs_value != before:
                raise PlanConflictError(f"{label} {name}: removed by ours, edited by theirs")
        else:
            append(theirs_value)


def _table(value: object) -> Table:
    table = tomlkit.table()
    if isinstance(value, dict):
        for field, entry in value.items():
            table[str(field)] = _item(entry)
    return table


def _fold_tables(label: str, fields: Key, documents: tuple[TOMLDocument, ...], name: str) -> None:
    found = [document.get(name) for document in documents]
    target = found[1]
    if not isinstance(target, AoT):
        return
    sides = tuple(items if isinstance(items, AoT) else [] for items in found)

    def replace(key: Key, value: object) -> None:
        for index, item in enumerate(target):
            if _key_of(item, fields) == key:
                target[index] = _table(value)

    _union(
        label,
        fields,
        (sides[0], sides[1], sides[2]),
        replace,
        lambda value: target.append(_table(value)),
    )


def _fold_array(label: str, fields: Key, documents: tuple[TOMLDocument, ...], name: str) -> None:
    found = [document.get(name) for document in documents]
    target = found[1]
    if not isinstance(target, Array):
        _fold_tables(label, fields, documents, name)
        return
    sides = tuple(items if isinstance(items, Array) else [] for items in found)

    def replace(key: Key, value: object) -> None:
        for index, item in enumerate(target):
            if _key_of(item, fields) == key:
                target[index] = _item(value)

    def append(value: object) -> None:
        target.add_line(_item(value), indent="  ")

    _union(label, fields, (sides[0], sides[1], sides[2]), replace, append)


def _merged(root: Path, relative: Path) -> TOMLDocument:
    documents = tuple(_stage(root, number, relative) for number in (1, 2, 3))
    if relative == PLAN:
        _fold_tables("step", ("id",), documents, "steps")
        _fold_tables("decision", ("id",), documents, "decisions")
    elif relative == IDS:
        _fold_array("issued id", ("id",), documents, "issued")
    elif relative == TRACE:
        _fold_array("trace source", ("id",), documents, "sources")
        _fold_array("trace candidate", ("source", "ref"), documents, "candidates")
    return documents[1]


def resolve(root: Path) -> tuple[str, ...]:
    """Each conflicted plan file merged by entry, validated together, then written and staged."""
    if _operation(root) == "none":
        raise PlanConflictError("no merge or rebase is in progress")
    files = (PLAN, IDS, TRACE)
    unmerged = set(_unmerged(root))
    conflicted = [relative for relative in files if str(relative) in unmerged]
    if not conflicted:
        raise PlanConflictError("no plan file is in conflict")
    documents: dict[Path, TOMLDocument] = {}
    for relative in files:
        if relative in conflicted:
            documents[relative] = _merged(root, relative)
        else:
            documents[relative] = tomlkit.parse((root / relative).read_text(encoding="utf-8"))
    try:
        rendered = _validated(documents)
    except ValueError as error:
        raise PlanConflictError(f"the merged plan fails its own validation: {error}") from error
    for relative in conflicted:
        (root / relative).write_text(rendered[relative], encoding="utf-8")
        git("add", "--", str(relative), cwd=root)
    return tuple(str(relative) for relative in conflicted)


class ResolvePlan(Contract):
    """plan-resolve/v1: what a resolution would act on, observed before it acts."""

    contract: Literal["plan-resolve/v1"] = "plan-resolve/v1"
    operation: Operation
    conflicted: tuple[str, ...]


def plan_resolve(root: Path) -> ResolvePlan:
    unmerged = set(_unmerged(root))
    names = tuple(str(relative) for relative in (PLAN, IDS, TRACE))
    conflicted = tuple(name for name in names if name in unmerged)
    return ResolvePlan(operation=_operation(root), conflicted=conflicted)


def run(root: Path) -> int:
    """plan:resolve on the spine: judged first, then resolved and staged (D.129)."""
    plan = plan_resolve(root)
    found = evaluate(plan, SUBJECT, POLICY, ENTRYPOINT)
    decision = decide(found)
    data = plan.model_dump(mode="json")
    if decision.action != "proceed":
        code = refusal_code(decision, "plan_resolve_refused")
        return enforce(announce(COMMAND, decision, code, reasons(found), data))
    try:
        resolved = resolve(root)
    except PlanConflictError as refused:
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, str(refused))
        return enforce(announce(COMMAND, stopped, "plan_conflict_refused", str(refused), data))
    message = f"resolved and staged {', '.join(resolved)}"
    return enforce(announce(COMMAND, decision, "plan_conflicts_resolved", message, data))


def main(argv: Sequence[str] | None = None) -> int:
    """The plan files of a stopped merge or rebase, resolved and staged, on the spine."""
    if list(sys.argv[1:] if argv is None else argv):
        stopped = halted(SUBJECT, ENTRYPOINT, POLICY, USAGE)
        return enforce(announce(COMMAND, stopped, "usage", USAGE, {}))
    return run(ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
