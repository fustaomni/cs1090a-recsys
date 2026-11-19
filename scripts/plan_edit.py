# scripts/plan_edit.py
"""Add and amend plan entries, preserving every comment (D.23, D.24).

THE 2026 STYLE-PRESERVING EDITOR. tomlkit round-trips all three plan files byte for
byte, so editing through it keeps every comment and layout -- where hand-made text
edits anchored on a guessed layout, and one was refused on a formatting difference.

VALUES ARE BUILT EXPLICITLY. Handed a plain list of dictionaries, tomlkit writes an
array of tables; lists become tomlkit arrays, multi-line when they hold tables, and
dictionaries become inline tables, matching the files' own style.

ALL OR NOTHING. Every edited document is re-read through its contract -- ProjectPlan,
IdLedger, PlanTrace -- before any file is written; any failure writes nothing.
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
import tomllib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import tomlkit
from pydantic import ConfigDict, Field, JsonValue, ValidationError
from tomlkit.items import AoT, Array, Item, Table
from tomlkit.toml_document import TOMLDocument

from command_outcome import CommandOutcome
from contract_base import Contract, from_document
from git_observe import GitObservationFailure, common_dir
from gitenv import git
from plan_models import IdLedger, PlanTrace, ProjectPlan
from plan_proofs import declares_proof

ROOT = Path(__file__).resolve().parent.parent
PLAN = Path("context") / "plan.toml"
IDS = Path("context") / "plan-ids.toml"
TRACE = Path("context") / "plan-trace.toml"
# EVERY ID THIS CLONE HAS ISSUED, IN THE DIRECTORY ALL ITS WORKTREES SHARE (D.162).
RESERVED = "plan-reservations"


class _Trace(Contract):
    source: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    text: str = Field(min_length=1)


class _Decline(Contract):
    """A decision declined: a choice not to do something, with its reason (D.338)."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class AddSpec(Contract):
    """What plan:add reads: new threads, new steps, and the one trace entry they map from."""

    # A NEW THREAD IS DECLARED WITH ITS STEPS (D.272): validated as a Thread by ProjectPlan,
    # in the same pass as the steps, so a project can plan work outside its first thread.
    threads: tuple[dict[str, JsonValue], ...] = ()
    steps: tuple[dict[str, JsonValue], ...] = ()
    # A DECLINE IS A DECISION OF ITS OWN (D.338): written declined, with its reason.
    decisions: tuple[_Decline, ...] = ()
    trace: _Trace


class AmendSpec(Contract):
    """What plan:amend reads: one step, and the fields to replace."""

    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(min_length=1)
    fields: dict[str, JsonValue] = Field(alias="set", min_length=1)


# TOML'S BARE-KEY ALPHABET. A key outside it must be quoted: a step id such as D.32,
# written bare, is the dotted key D -> 32, and the contract refuses that nested table.
# Every plan key that is a step id holds a dot, so without this no because could be
# written at all (D.51).
_BARE_KEY = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")


def _key(name: str) -> str:
    """A key as TOML text: bare when TOML allows it, else a basic string with TOML's escaping."""
    if name and set(name) <= _BARE_KEY:
        return name
    return tomlkit.item(name).as_string()


def _render(value: JsonValue) -> str:
    """A value as TOML text in the plan files' own style.

    { key = value } with a space inside the braces, always on one line as TOML
    requires; a multi-line array, two-space indented, when it holds tables; scalars
    through tomlkit, so strings get TOML's own escaping.
    """
    if isinstance(value, dict):
        pairs = ", ".join(f"{_key(key)} = {_render(item)}" for key, item in value.items())
        return "{ " + pairs + " }"
    if isinstance(value, list):
        if any(isinstance(item, dict) for item in value):
            return "[\n" + "".join(f"  {_render(item)},\n" for item in value) + "]"
        return "[" + ", ".join(_render(item) for item in value) + "]"
    return tomlkit.item(value).as_string()


def _value(value: JsonValue) -> Item:
    """Parsed by tomlkit from text in the files' style, so it keeps that whitespace exactly."""
    parsed = tomlkit.parse(f"value = {_render(value)}\n")["value"]
    if not isinstance(parsed, Item):
        raise SystemExit("a rendered value did not parse as a TOML item")
    return parsed


def _parse(root: Path, relative: Path) -> TOMLDocument:
    return tomlkit.parse((root / relative).read_text(encoding="utf-8"))


def _array(document: TOMLDocument, key: str) -> Array:
    found = document[key]
    if not isinstance(found, Array):
        raise SystemExit(f"{key} is not an inline array")
    return found


def _steps(document: TOMLDocument) -> AoT:
    found = document["steps"]
    if not isinstance(found, AoT):
        raise SystemExit("steps is not an array of tables")
    return found


def _validated(documents: dict[Path, TOMLDocument]) -> dict[Path, str]:
    """Each document rendered and re-read through its contract; raises on any failure."""
    rendered = {relative: tomlkit.dumps(document) for relative, document in documents.items()}
    from_document(ProjectPlan, tomllib.loads(rendered[PLAN]))
    if IDS in rendered:
        from_document(IdLedger, tomllib.loads(rendered[IDS]))
    if TRACE in rendered:
        from_document(PlanTrace, tomllib.loads(rendered[TRACE]))
    return rendered


def _errors(error: ValidationError) -> list[JsonValue]:
    """Every validation error as data: the field's path, pydantic's message and its type.

    "1 validation error" says that something failed; these say what, and for a value
    outside a fixed set the message names the values the contract accepts.
    """
    return [
        {
            "field": ".".join(str(part) for part in detail["loc"]),
            "message": detail["msg"],
            "type": detail["type"],
        }
        for detail in error.errors(include_url=False)
    ]


def _report(command: str, outcome: str, code: str, message: str, data: dict[str, JsonValue]) -> int:
    envelope = CommandOutcome.model_validate(
        {"command": command, "outcome": outcome, "code": code, "message": message, "data": data}
    )
    print(json.dumps(envelope.model_dump(), indent=2))
    return envelope.exit_code


def _summary(error: ValidationError) -> str:
    """Each validation error as `field: message`, joined: never the count line alone (A.128)."""
    return "; ".join(
        f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}"
        for detail in error.errors(include_url=False)
    )


def _read_spec[S: Contract](model: type[S], argv: Sequence[str] | None, verb: str) -> S | int:
    """The verb's spec as its contract, or its refusal reported and that exit code (A.128).

    Every verb refuses an invalid spec as spec_invalid and one that cannot be read or parsed
    as TOML as spec_unreadable: a closed outcome to branch on, never a traceback.
    """
    command = f"plan:{verb}"
    try:
        return from_document(model, tomllib.loads(_spec_text(argv, verb)))
    except ValidationError as error:
        data: dict[str, JsonValue] = {"errors": _errors(error)}
        return _report(command, "refused", "spec_invalid", _summary(error), data)
    except (OSError, tomllib.TOMLDecodeError) as error:
        return _report(command, "refused", "spec_unreadable", str(error), {})


def _spec_text(argv: Sequence[str] | None, verb: str) -> str:
    args = list(sys.argv[2:] if argv is None else argv)
    if len(args) != 1:
        raise SystemExit(f"usage: mise run run plan:{verb} <spec.toml>")
    return Path(args[0]).read_text(encoding="utf-8")


def _issued_elsewhere(root: Path) -> dict[str, str] | None:
    """Each id the ledger at a remote-tracking ref holds, with the first ref holding it (D.330).

    Without origin there is no other branch to read. A fetch that fails is None, so no id is
    assumed free on branches that could not be seen.
    """
    if "origin" not in git("remote", cwd=root).stdout.split():
        return {}
    if git("fetch", "--quiet", "--prune", "origin", cwd=root).returncode != 0:
        return None
    refs = git("for-each-ref", "--format=%(refname)", "refs/remotes/", cwd=root).stdout
    found: dict[str, str] = {}
    for ref in refs.split():
        shown = git("show", "--end-of-options", f"{ref}:{IDS.as_posix()}", cwd=root)
        if shown.returncode != 0:
            continue
        ledger = from_document(IdLedger, tomllib.loads(shown.stdout))
        for entry in ledger.issued:
            found.setdefault(entry.id, ref)
    return found


def _common(root: Path) -> Path | None:
    """The clone's common directory, which every worktree shares; None outside git (D.162)."""
    found = common_dir(root)
    return None if isinstance(found, GitObservationFailure) else found


@contextmanager
def _locked(common: Path | None) -> Iterator[None]:
    """ONE WRITER AT A TIME (D.162): the lock spans the read, every check and the write."""
    if common is None:
        yield
        return
    with (common / "plan-edit.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _reserved(common: Path | None, ids: Sequence[str]) -> list[str]:
    """Every id another worktree of this clone has already issued (D.162)."""
    if common is None:
        return []
    return [new for new in ids if (common / RESERVED / new).exists()]


def _reserve(common: Path | None, ids: Sequence[str]) -> None:
    """Each id just issued, reserved for the whole clone."""
    if common is None:
        return
    (common / RESERVED).mkdir(exist_ok=True)
    for new in ids:
        (common / RESERVED / new).touch()


def _write_all(root: Path, rendered: dict[Path, str], before: dict[Path, bytes]) -> str | None:
    """Every file replaced, or every one restored, so the three never disagree (D.162)."""
    done: list[Path] = []
    for relative, text in rendered.items():
        staged = root / relative.with_name(relative.name + ".new")
        try:
            staged.write_text(text, encoding="utf-8")
            os.replace(staged, root / relative)
        except OSError as failure:
            staged.unlink(missing_ok=True)
            for kept in done:
                (root / kept).write_bytes(before[kept])
            return f"{relative}: {failure}"
        done.append(relative)
    return None


def add(argv: Sequence[str] | None = None, *, root: Path = ROOT) -> int:
    """plan:add <spec> -- threads, steps, their ids and one trace entry, all or nothing."""
    spec = _read_spec(AddSpec, argv, "add")
    if isinstance(spec, int):
        return spec
    common = _common(root)
    with _locked(common):
        return _add(spec, root, common)


def _add(spec: AddSpec, root: Path, common: Path | None) -> int:
    """The add itself, under the clone's lock."""
    documents = {relative: _parse(root, relative) for relative in (PLAN, IDS, TRACE)}
    before = {relative: (root / relative).read_bytes() for relative in (PLAN, IDS, TRACE)}
    planned = {str(step["id"]) for step in _steps(documents[PLAN])}
    issued = {str(entry["id"]) for entry in _array(documents[IDS], "issued")}
    if not spec.steps and not spec.decisions:
        message = "a spec adds at least one step or one decision"
        return _report("plan:add", "refused", "spec_empty", message, {})
    new_ids = [str(step.get("id", "")) for step in spec.steps]
    new_ids += [declined.id for declined in spec.decisions]
    taken = sorted(set(new_ids) & (planned | issued))
    if taken:
        return _report(
            "plan:add",
            "refused",
            "id_taken",
            f"already planned or issued: {', '.join(taken)}",
            {"taken": list(taken)},
        )
    # EVERY NEW STEP NAMES A PROOF (D.266), judged offline, before origin is fetched.
    unproven = [
        str(step.get("id", "")) for step in spec.steps if not declares_proof(step.get("done_when"))
    ]
    if unproven:
        return _report(
            "plan:add",
            "refused",
            "proof_missing",
            f"{', '.join(unproven)}: no proof in done_when; a task or a file shows an artefact, "
            "not that a rule holds",
            {"steps": list(unproven)},
        )
    # ACROSS EVERY PUSHED BRANCH (D.330): another machine's ids exist only on its own branch.
    elsewhere = _issued_elsewhere(root)
    if elsewhere is None:
        return _report(
            "plan:add",
            "refused",
            "ids_unverified",
            "origin could not be fetched, so ids issued on other branches are unknown",
            {"remote": "origin"},
        )
    clashing: dict[str, JsonValue] = {new: elsewhere[new] for new in new_ids if new in elsewhere}
    if clashing:
        named = ", ".join(f"{new} at {elsewhere[new]}" for new in sorted(clashing))
        return _report(
            "plan:add",
            "refused",
            "id_issued_elsewhere",
            f"already issued on another branch: {named}",
            {"taken": clashing},
        )
    reserved = _reserved(common, new_ids)
    if reserved:
        message = f"reserved by another worktree of this clone: {', '.join(reserved)}"
        return _report("plan:add", "refused", "id_reserved", message, {"taken": list(reserved)})
    existing = {str(thread["id"]) for thread in _array(documents[PLAN], "threads")}
    declared = [str(thread.get("id", "")) for thread in spec.threads]
    reused = sorted(set(declared) & existing)
    if reused:
        return _report(
            "plan:add",
            "refused",
            "thread_taken",
            f"threads already declared: {', '.join(reused)}",
            {"taken": list(reused)},
        )
    # REFUSED AS DATA, BEFORE ANY WRITE: never left to surface as a contract error.
    known = existing | set(declared)
    for step in spec.steps:
        thread = str(step.get("thread", ""))
        if thread not in known:
            named = str(step.get("id", ""))
            return _report(
                "plan:add",
                "refused",
                "thread_undeclared",
                f"{named} names thread {thread}, which neither the plan nor the spec declares",
                {"step": named, "thread": thread},
            )

    for entry in spec.threads:
        _array(documents[PLAN], "threads").add_line(_value(entry), indent="  ")
    for step in spec.steps:
        table = tomlkit.table()
        for key, value in step.items():
            table[key] = _value(value)
        _steps(documents[PLAN]).append(table)
        _array(documents[IDS], "issued").add_line(
            _value({"id": step["id"], "first_title": step.get("title", "")}), indent="  "
        )
    if spec.decisions and "decisions" not in documents[PLAN]:
        documents[PLAN].append("decisions", tomlkit.aot())
    for declined in spec.decisions:
        decisions = documents[PLAN]["decisions"]
        if not isinstance(decisions, AoT):
            raise SystemExit("decisions is not an array of tables")
        table = tomlkit.table()
        table.add("id", declined.id)
        table.add("title", declined.title)
        table.add("state", "declined")
        table.add("reason", declined.reason)
        decisions.append(table)
        _array(documents[IDS], "issued").add_line(
            _value({"id": declined.id, "first_title": declined.title}), indent="  "
        )
    _array(documents[TRACE], "candidates").add_line(
        _value({**spec.trace.model_dump(), "maps_to": list(new_ids)}), indent="  "
    )
    try:
        rendered = _validated(documents)
    except ValidationError as error:
        return _report(
            "plan:add",
            "refused",
            "contract_violated",
            str(error).splitlines()[0],
            {"ids": list(new_ids), "errors": _errors(error)},
        )
    changed = [
        str(relative) for relative, read in before.items() if (root / relative).read_bytes() != read
    ]
    if changed:
        message = f"changed since it was read: {', '.join(changed)}"
        return _report("plan:add", "refused", "plan_changed", message, {"changed": list(changed)})
    failure = _write_all(root, rendered, before)
    if failure is not None:
        return _report("plan:add", "refused", "write_failed", failure, {"ids": list(new_ids)})
    _reserve(common, new_ids)
    return _report(
        "plan:add",
        "success",
        "entries_added",
        f"added {', '.join(new_ids)}",
        {"ids": list(new_ids)},
    )


def _entries(document: TOMLDocument) -> list[Table]:
    """Every plan entry that has an id: steps, then decisions."""
    entries: list[Table] = []
    for key in ("steps", "decisions"):
        found = document.get(key)
        if isinstance(found, AoT):
            entries.extend(found)
    return entries


def amend(argv: Sequence[str] | None = None, *, root: Path = ROOT) -> int:
    """plan:amend <spec> -- replace named fields of one step or decision, in place."""
    spec = _read_spec(AmendSpec, argv, "amend")
    if isinstance(spec, int):
        return spec
    document = _parse(root, PLAN)
    target = next((t for t in _entries(document) if t["id"] == spec.id), None)
    if target is None:
        return _report(
            "plan:amend",
            "refused",
            "entry_unknown",
            f"{spec.id} is not a step or a decision",
            {"id": spec.id},
        )
    had_proof = declares_proof(target.get("done_when"))
    for key, value in spec.fields.items():
        target[key] = _value(value)
    # A PROVEN STEP STAYS PROVEN (D.266): an amend never takes its last proof away.
    if had_proof and not declares_proof(target.get("done_when")):
        return _report(
            "plan:amend",
            "refused",
            "last_proof_removed",
            f"{spec.id} declares a proof, and this amend would leave it none",
            {"id": spec.id},
        )
    try:
        rendered = _validated({PLAN: document})
    except ValidationError as error:
        return _report(
            "plan:amend",
            "refused",
            "contract_violated",
            str(error).splitlines()[0],
            {"id": spec.id, "errors": _errors(error)},
        )
    (root / PLAN).write_text(rendered[PLAN], encoding="utf-8")
    return _report(
        "plan:amend",
        "success",
        "entry_amended",
        f"{spec.id}: {', '.join(spec.fields)}",
        {"id": spec.id, "fields": list(spec.fields)},
    )


class TraceSpec(Contract):
    """What plan:record reads: new sources, and candidates that need no new step (D.114)."""

    sources: tuple[dict[str, JsonValue], ...] = ()
    candidates: tuple[dict[str, JsonValue], ...] = Field(min_length=1)


def _mapped(candidate: dict[str, JsonValue]) -> list[str]:
    """The step ids a candidate maps to, as written in the spec."""
    maps = candidate.get("maps_to", [])
    return [str(step) for step in maps] if isinstance(maps, list) else []


def record(argv: Sequence[str] | None = None, *, root: Path = ROOT) -> int:
    """plan:record <spec> -- sources, and candidates mapped to planned steps or declared not."""
    spec = _read_spec(TraceSpec, argv, "record")
    if isinstance(spec, int):
        return spec
    documents = {relative: _parse(root, relative) for relative in (PLAN, TRACE)}
    planned = {str(step["id"]) for step in _steps(documents[PLAN])}
    named = {step for candidate in spec.candidates for step in _mapped(candidate)}
    unplanned = sorted(named - planned)
    if unplanned:
        return _report(
            "plan:record",
            "refused",
            "step_unknown",
            f"not planned: {', '.join(unplanned)}",
            {"unplanned": list(unplanned)},
        )
    text = (root / TRACE).read_text(encoding="utf-8")
    seen = {(c.source, c.ref) for c in from_document(PlanTrace, tomllib.loads(text)).candidates}
    new = [(str(c.get("source", "")), str(c.get("ref", ""))) for c in spec.candidates]
    repeated = sorted((set(new) & seen) | {pair for pair in new if new.count(pair) > 1})
    if repeated:
        listed = [f"{source} {ref}" for source, ref in repeated]
        return _report(
            "plan:record",
            "refused",
            "candidate_exists",
            f"already recorded: {', '.join(listed)}",
            {"repeated": list(listed)},
        )
    for source in spec.sources:
        _array(documents[TRACE], "sources").add_line(_value(source), indent="  ")
    for candidate in spec.candidates:
        _array(documents[TRACE], "candidates").add_line(_value(candidate), indent="  ")
    try:
        rendered = _validated(documents)
    except ValidationError as error:
        return _report(
            "plan:record",
            "refused",
            "contract_violated",
            str(error).splitlines()[0],
            {"errors": _errors(error)},
        )
    (root / TRACE).write_text(rendered[TRACE], encoding="utf-8")
    recorded = [f"{source} {ref}" for source, ref in new]
    return _report(
        "plan:record",
        "success",
        "trace_recorded",
        f"recorded {len(recorded)} candidate(s)",
        {"candidates": list(recorded)},
    )


class _Retraction(Contract):
    source: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RetractSpec(Contract):
    """What plan:retract reads: candidates to withdraw, each with its reason (D.131)."""

    candidates: tuple[_Retraction, ...] = Field(min_length=1)


class _Retirement(Contract):
    """One step to retire, and why."""

    id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RetireSpec(Contract):
    """plan:retire's spec: the steps to supersede, each with its reason (D.260)."""

    steps: tuple[_Retirement, ...] = Field(min_length=1)


def retire(argv: Sequence[str] | None = None, *, root: Path = ROOT) -> int:
    """plan:retire <spec> -- supersede steps with their reasons, keeping every id (D.260).

    A retired step becomes a decision with the same id and title, state superseded, so the
    commits naming it still trace to it and its ledger entry stays issued. The plan's own
    model refuses a step a live step still depends on; nothing is written unless all holds.
    """
    spec = _read_spec(RetireSpec, argv, "retire")
    if isinstance(spec, int):
        return spec
    documents = {PLAN: _parse(root, PLAN)}
    steps = _steps(documents[PLAN])
    reasons = {r.id: r.reason for r in spec.steps}
    live = {str(entry["id"]) for entry in steps if isinstance(entry, dict)}
    not_live = sorted(set(reasons) - live)
    if not_live:
        return _report(
            "plan:retire",
            "refused",
            "step_unknown",
            f"not a live step: {', '.join(not_live)}",
            {"unknown": list(not_live)},
        )
    if "decisions" not in documents[PLAN]:
        documents[PLAN].append("decisions", tomlkit.aot())
    decisions = documents[PLAN]["decisions"]
    if not isinstance(decisions, AoT):
        raise SystemExit("decisions is not an array of tables")
    for index in reversed(range(len(steps))):
        entry = steps[index]
        if str(entry["id"]) in reasons:
            step_id = str(entry["id"])
            decision = tomlkit.table()
            decision.add("id", step_id)
            decision.add("title", str(entry["title"]))
            decision.add("state", "superseded")
            decision.add("reason", reasons[step_id])
            decisions.append(decision)
            del steps[index]
    try:
        checked = _validated(documents)
    except ValidationError as error:
        first = str(error).splitlines()[0]
        return _report("plan:retire", "refused", "contract_violated", first, {})
    (root / PLAN).write_text(checked[PLAN], encoding="utf-8")
    retired = [f"{r.id}: {r.reason}" for r in spec.steps]
    return _report(
        "plan:retire",
        "success",
        "steps_retired",
        f"retired {len(retired)} step(s)",
        {"retired": list(retired)},
    )


def retract(argv: Sequence[str] | None = None, *, root: Path = ROOT) -> int:
    """plan:retract <spec> -- withdraw candidates, never leaving a step untraced."""
    from plan_models import untraced

    spec = _read_spec(RetractSpec, argv, "retract")
    if isinstance(spec, int):
        return spec
    documents = {relative: _parse(root, relative) for relative in (PLAN, TRACE)}
    text = (root / TRACE).read_text(encoding="utf-8")
    current = from_document(PlanTrace, tomllib.loads(text)).candidates
    recorded = {(c.source, c.ref) for c in current}
    wanted = {(r.source, r.ref) for r in spec.candidates}
    unknown = sorted(wanted - recorded)
    if unknown:
        listed = [f"{source} {ref}" for source, ref in unknown]
        return _report(
            "plan:retract",
            "refused",
            "candidate_unknown",
            f"not recorded: {', '.join(listed)}",
            {"unknown": list(listed)},
        )
    candidates = _array(documents[TRACE], "candidates")
    for index in reversed(range(len(candidates))):
        entry = candidates[index]
        if isinstance(entry, dict) and (str(entry["source"]), str(entry["ref"])) in wanted:
            del candidates[index]
    try:
        rendered = _validated(documents)
    except ValidationError as error:
        first = str(error).splitlines()[0]
        return _report("plan:retract", "refused", "contract_violated", first, {})
    plan = from_document(ProjectPlan, tomllib.loads(rendered[PLAN]))
    broken = untraced(from_document(PlanTrace, tomllib.loads(rendered[TRACE])), plan)
    if broken:
        return _report(
            "plan:retract",
            "refused",
            "trace_broken",
            "; ".join(broken),
            {"untraced": list(broken)},
        )
    (root / TRACE).write_text(rendered[TRACE], encoding="utf-8")
    withdrawn = [f"{r.source} {r.ref}: {r.reason}" for r in spec.candidates]
    return _report(
        "plan:retract",
        "success",
        "trace_retracted",
        f"retracted {len(withdrawn)} candidate(s)",
        {"retracted": list(withdrawn)},
    )


if __name__ == "__main__":
    verbs = {"add": add, "amend": amend, "record": record, "retract": retract, "retire": retire}
    if len(sys.argv) < 2 or sys.argv[1] not in verbs:
        raise SystemExit("usage: plan_edit.py add|amend|record|retract <spec.toml>")
    sys.exit(verbs[sys.argv[1]]())
