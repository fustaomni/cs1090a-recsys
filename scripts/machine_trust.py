"""machine:trust -- a checkout's mise.toml is trusted only after the founding gate (A.27).

UNDER PARANOID, A CHANGED mise.toml IS UNTRUSTED, and mise then runs no task from it, a trust
task included. So the gate and the trust are one operation: source:apply calls it the moment it
writes mise.toml, and machine:trust calls it for a checkout nothing wrote. The founding policy
judges the text first; only on allow is `mise trust` run, on that checkout's own file by its own
path, so a linked worktree is never trusted through its main checkout. Each trust is logged.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from contract_base import Contract

ROOT = Path(__file__).resolve().parent.parent
FOUNDING = ROOT / "policies" / "founding"
QUERY = "data.founding.mise.allow"
OPA = "opa@1.21.1"
EVENTS = Path.home() / ".cache" / "founding" / "trust-events.tsv"
Runner = Callable[[list[str], Path, str | None], subprocess.CompletedProcess[str]]


class TrustDecision(Contract):
    """trust-decision/v1: one checkout's mise.toml, judged by the founding gate, then trusted."""

    contract: Literal["trust-decision/v1"] = "trust-decision/v1"
    config: str
    sha256: str
    allowed: bool
    trusted: bool


def _run(command: list[str], cwd: Path, stdin: str | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, input=stdin, capture_output=True, text=True, check=False
    )


def founding_allows(text: str, *, run: Runner = _run) -> bool:
    """Whether the founding policy allows this mise.toml text, judged from outside any project."""
    command = [
        "mise",
        "exec",
        OPA,
        "--",
        "opa",
        "eval",
        "--format",
        "raw",
        "--stdin-input",
        "-d",
        str(FOUNDING),
        QUERY,
    ]
    done = run(command, Path.home(), json.dumps(tomllib.loads(text)))
    return done.returncode == 0 and done.stdout.strip() == "true"


def trust(
    checkout: Path,
    text: str,
    *,
    allows: Callable[[str], bool] = founding_allows,
    run: Runner = _run,
    events: Path = EVENTS,
) -> TrustDecision:
    """Gate this checkout's mise.toml text; only on allow, trust that file by its own path."""
    config = (checkout / "mise.toml").resolve()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    allowed = allows(text)
    trusted = allowed and run(["mise", "trust", str(config)], Path.home(), None).returncode == 0
    if trusted:
        events.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with events.open("a", encoding="utf-8") as log:
            log.write(f"{stamp}\ttrust\t{config}\tsha256={digest}\tby={getpass.getuser()}\n")
    return TrustDecision(config=str(config), sha256=digest, allowed=allowed, trusted=trusted)


def main(argv: Sequence[str] | None = None) -> int:
    """machine:trust [<checkout>] -- gate and trust a checkout's mise.toml as it stands on disk.

    With no argument it is this checkout. With one it is that checkout, judged and trusted by its
    own path, so a trusted worktree trusts another without mise ever loading the other (A.122).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        raise SystemExit(f"usage: machine:trust [<checkout>]  (got {args})")
    checkout = Path(args[0]).expanduser().resolve() if args else ROOT
    config = checkout / "mise.toml"
    if not config.is_file():
        raise SystemExit(f"{checkout} holds no mise.toml, so there is nothing to trust")
    decision = trust(checkout, config.read_text(encoding="utf-8"))
    print(decision.model_dump_json(indent=2))
    return 0 if decision.trusted else 2


if __name__ == "__main__":
    raise SystemExit(main())
