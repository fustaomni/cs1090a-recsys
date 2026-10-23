"""model:fit (A.100): a fitted model is a governed artifact, declared, recorded and judged.

A FITTED PARAMETER MEANS NOTHING WITHOUT ITS ORIGIN. A declaration fixes what a fit may read
(the data's fingerprint, the features and whether each is point-in-time, the time cutoffs) and
how it must be made (method, scaler, hyperparameters, seed). A record states what one fit
actually read, did and produced, with its artifact's digest. runs.model_run judges the record
against the declaration, and a model is scored only when that verdict passes for its digest.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field

import spine
from command_outcome import CommandOutcome
from contract_base import Contract
from gitenv import git
from run_ledger import default_ledger

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "policies" / "runs" / "model_run"
ENTRYPOINT = "data.runs.model_run.deny"
SUBJECT = "model_run"


class Feature(Contract):
    """One input a model may read, and whether it uses only data before each row's time."""

    name: str = Field(min_length=1)
    point_in_time: bool


class Cutoffs(Contract):
    """The validation and test cutoffs, as quantiles of the rating timestamps."""

    validation: float = Field(gt=0, lt=1)
    test: float = Field(gt=0, lt=1)


class Declaration(Contract):
    """model-run-declaration/v1: what a fit may read, and how it must be made."""

    contract: Literal["model-run-declaration/v1"] = "model-run-declaration/v1"
    model: str = Field(min_length=1)
    method: str = Field(min_length=1)
    features: tuple[Feature, ...]
    cutoffs: Cutoffs
    scaler: str = Field(min_length=1)
    hyperparameters: dict[str, float]
    seed: int
    data_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FitRecord(Contract):
    """model-run/v1: what one fit actually read, did and produced, beside its declaration."""

    contract: Literal["model-run/v1"] = "model-run/v1"
    declared: Declaration
    model: str
    method: str
    features: tuple[Feature, ...]
    scaler: str
    data_sha256: str
    first_row: int
    last_row: int
    last_training_time: int
    validation_cutoff_time: int
    parameters: dict[str, float]
    metrics: dict[str, float]
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    head: str


Rating = tuple[int, int, int, int]


def read_ratings(ratings: Path) -> list[Rating]:
    """ratings.dat rows (user, movie, rating, time) in time order; ties keep file order."""
    rows: list[Rating] = []
    for line in ratings.read_text(encoding="latin-1").splitlines():
        if not line.strip():
            continue
        user, movie, rating, time = line.split("::")
        rows.append((int(user), int(movie), int(rating), int(time)))
    return sorted(rows, key=lambda row: row[3])


def cut_index(times: list[int], quantile: float) -> int:
    """The first row at or after the quantile, moved past any rating sharing its time."""
    index = min(len(times), math.ceil(quantile * len(times)))
    while 0 < index < len(times) and times[index] == times[index - 1]:
        index += 1
    return index


def canonical(document: dict[str, object]) -> bytes:
    """Canonical JSON (sorted keys, compact): the bytes whose SHA-256 names the artifact."""
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _biases(rows: list[Rating], shrink_user: float, shrink_movie: float) -> dict[str, object]:
    mu = sum(row[2] for row in rows) / len(rows)
    user_sum: dict[int, float] = {}
    user_count: dict[int, int] = {}
    for user, _, rating, _ in rows:
        user_sum[user] = user_sum.get(user, 0.0) + rating - mu
        user_count[user] = user_count.get(user, 0) + 1
    users = {u: user_sum[u] / (user_count[u] + shrink_user) for u in user_sum}
    movie_sum: dict[int, float] = {}
    movie_count: dict[int, int] = {}
    for user, movie, rating, _ in rows:
        movie_sum[movie] = movie_sum.get(movie, 0.0) + rating - mu - users[user]
        movie_count[movie] = movie_count.get(movie, 0) + 1
    movies = {m: movie_sum[m] / (movie_count[m] + shrink_movie) for m in movie_sum}
    return {
        "global_mean": mu,
        "user_bias": {str(u): b for u, b in sorted(users.items())},
        "movie_bias": {str(m): b for m, b in sorted(movies.items())},
    }


def _predict(model: dict[str, object], user: int, movie: int) -> float:
    mu = model["global_mean"]
    users = model["user_bias"]
    movies = model["movie_bias"]
    if not isinstance(mu, float) or not isinstance(users, dict) or not isinstance(movies, dict):
        raise SystemExit("model_run: a fitted model lost its shape")
    return mu + float(users.get(str(user), 0.0)) + float(movies.get(str(movie), 0.0))


def fit(declaration: Declaration, ratings: Path, artifact: Path, head: str) -> FitRecord:
    """Fit on the rows before the validation cutoff only, and record what the fit did."""
    rows = read_ratings(ratings)
    times = [row[3] for row in rows]
    start = cut_index(times, declaration.cutoffs.validation)
    end = cut_index(times, declaration.cutoffs.test)
    training = rows[:start]
    model = _biases(
        training,
        declaration.hyperparameters["shrink_user"],
        declaration.hyperparameters["shrink_movie"],
    )
    validation = rows[start:end]
    metrics: dict[str, float] = {}
    if validation:
        squared = sum((_predict(model, u, m) - r) ** 2 for u, m, r, _ in validation)
        metrics["validation_rmse"] = math.sqrt(squared / len(validation))
    body = canonical({"model": declaration.model, **model})
    artifact.write_bytes(body)
    users = model["user_bias"]
    movies = model["movie_bias"]
    return FitRecord(
        declared=declaration,
        model=declaration.model,
        method=declaration.method,
        features=declaration.features,
        scaler=declaration.scaler,
        data_sha256=hashlib.sha256(ratings.read_bytes()).hexdigest(),
        first_row=0,
        last_row=start - 1,
        last_training_time=training[-1][3],
        validation_cutoff_time=rows[start][3] if start < len(rows) else training[-1][3] + 1,
        parameters={
            "global_mean": float(str(model["global_mean"])),
            "users": float(len(users) if isinstance(users, dict) else 0),
            "movies": float(len(movies) if isinstance(movies, dict) else 0),
        },
        metrics=metrics,
        artifact_sha256=hashlib.sha256(body).hexdigest(),
        head=head,
    )


def admit(record: FitRecord, artifact: Path) -> list[str]:
    """The refusals that keep a model from scoring; an empty list is the only admission."""
    refusals: list[str] = []
    bound = artifact.exists() and (
        hashlib.sha256(artifact.read_bytes()).hexdigest() == record.artifact_sha256
    )
    if not bound:
        refusals.append("ERR_MODEL_ARTIFACT_UNBOUND")
    found = spine.evaluate(record, SUBJECT, POLICY, ENTRYPOINT)
    refusals.extend(rule.code for rule in found.rules if rule.outcome == "fail")
    return sorted(refusals)


BASELINE = ROOT / "contracts" / "model-runs" / "baseline.toml"


def load(declaration: Path) -> Declaration:
    """A declaration file, validated once at the boundary.

    Through JSON, not Python: TOML's arrays arrive as lists, which strict validation refuses
    for a tuple field from Python but accepts from JSON, so every other check stays strict.
    """
    with declaration.open("rb") as handle:
        document = tomllib.load(handle)
    return Declaration.model_validate_json(json.dumps(document))


def run(declaration: Path, ratings: Path, out: Path, head: str) -> tuple[FitRecord, list[str]]:
    """Fit as declared, write the artifact and its record into out, and judge them.

    The record is written even when the fit is refused: a refusal is evidence too.
    """
    declared = load(declaration)
    out.mkdir(parents=True, exist_ok=True)
    artifact = out / f"{declared.model}.json"
    record = fit(declared, ratings, artifact, head)
    written = out / f"{declared.model}.record.json"
    written.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return record, admit(record, artifact)


def fit_from(
    declaration: Path, ratings: Path, out: Path, head: str, clean: bool
) -> tuple[FitRecord | None, list[str]]:
    """Fit only from committed code: a record must name the exact code that produced it."""
    if not clean:
        return None, ["ERR_MODEL_TREE_DIRTY"]
    return run(declaration, ratings, out, head)


def tree(root: Path) -> tuple[str, bool]:
    """HEAD, and whether tracked files are unchanged, through the scrubbed git helper.

    Untracked files are not code here (.artifacts, build output), so they are not counted.
    """
    head = git("rev-parse", "HEAD", cwd=root)
    status = git("status", "--porcelain", "--untracked-files=no", cwd=root)
    if head.returncode != 0 or status.returncode != 0:
        raise SystemExit(f"model_run: git could not report the tree: {status.stderr.strip()}")
    return head.stdout.strip(), status.stdout.strip() == ""


def _announce(outcome: str, code: str, message: str, data: dict[str, object]) -> int:
    envelope = CommandOutcome.model_validate(
        {
            "command": "model:fit",
            "outcome": outcome,
            "code": code,
            "message": message,
            "data": data,
        }
    )
    print(json.dumps(envelope.model_dump(), indent=2))
    return envelope.exit_code


def main() -> int:
    evidence = default_ledger().parent.parent
    ratings = evidence / "data" / "ml-1m" / "ratings.dat"
    out = evidence / "model-runs"
    data: dict[str, object] = {"declaration": str(BASELINE), "ratings": str(ratings)}
    if not ratings.exists():
        return _announce("refused", "data_missing", f"{ratings} is missing: run data:fetch", data)
    head, clean = tree(ROOT)
    record, refusals = fit_from(BASELINE, ratings, out, head, clean)
    if record is not None:
        data["record"] = record.model_dump(mode="json")
    if record is None or refusals:
        return _announce("refused", "fit_refused", ", ".join(refusals), data)
    message = f"{record.model} fitted on {record.last_row + 1} rows and admitted into {out}"
    return _announce("success", "fitted", message, data)


if __name__ == "__main__":
    sys.exit(main())
