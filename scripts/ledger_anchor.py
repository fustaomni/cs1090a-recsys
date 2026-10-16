"""ledger:anchor -- the ledger's newest record is anchored where its writer cannot reach (A.87).

A hash chain shows an edited or deleted record, but cutting its newest records leaves a valid,
shorter chain. The anchor asserts that the record at a position has a given run id and digest; it
is committed and pushed, so a truncation is caught by any checkout holding a newer anchor than the
ledger can satisfy. It moves only forward, and never past an anchor that no longer holds, since
advancing over a broken one would launder the truncation it exposes. Nothing is written here: the
anchor is planned as a source-apply/v1 spec for source:apply.
"""

from __future__ import annotations

import sys
from pathlib import Path

from run_ledger import ANCHOR, LedgerAnchor, RunRecord, declared_anchor, default_ledger, verify

ROOT = Path(__file__).resolve().parent.parent
TRIPLE = "'" * 3
USAGE = "usage: ledger_anchor.py --out <spec.toml>"


def _toml(anchor: LedgerAnchor) -> str:
    return (
        "# contracts/ledger-anchor.toml\n"
        "# ledger-anchor/v1 (A.87), written only by ledger:anchor.\n"
        "# The run ledger's record at this position has this run id and digest.\n"
        "# It never moves backwards, nor past an anchor that no longer holds.\n"
        f'contract = "{anchor.contract}"\n'
        f'ledger = "{anchor.ledger}"\n'
        f"position = {anchor.position}\n"
        f'run_id = "{anchor.run_id}"\n'
        f'sha256 = "{anchor.sha256}"\n'
    )


def plan(root: Path, ledger: Path) -> str:
    """The spec moving the anchor to the ledger's newest record, after every check has held."""
    current = declared_anchor(root)
    if current is not None and current.ledger != str(ledger):
        raise SystemExit(f"the anchor names {current.ledger}, not {ledger}; nothing is anchored")
    report = verify(ledger, anchor=current)
    if not report.intact:
        raise SystemExit(f"the ledger breaks at record {report.broken_at}; nothing is anchored")
    if report.anchor_broken:
        raise SystemExit("the anchor no longer holds; advancing it would hide a truncation")
    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise SystemExit(f"{ledger} holds no record to anchor")
    head = RunRecord.model_validate_json(lines[-1])
    anchor = LedgerAnchor(
        ledger=str(ledger), position=len(lines), run_id=head.run_id, sha256=head.sha256
    )
    text = _toml(anchor)
    target = root / ANCHOR
    path = ANCHOR.as_posix()
    if target.exists():
        old = target.read_text(encoding="utf-8")
        body = f'op = "replace"\npath = "{path}"\n'
        body += f"anchor = {TRIPLE}\n{old}{TRIPLE}\nreplacement = {TRIPLE}\n{text}{TRIPLE}\n"
    else:
        body = f'op = "create"\npath = "{path}"\ncontent = {TRIPLE}\n{text}{TRIPLE}\n'
    return f'contract = "source-apply/v1"\n\n[[operations]]\n{body}'


def main() -> int:
    match sys.argv[1:]:
        case ["--out", out] if Path(out).parts[:1] == (".artifacts",):
            target = ROOT / out
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(plan(ROOT, default_ledger()), encoding="utf-8")
            print(f"planned the ledger anchor into {out}; apply it with source:apply {out}")
            return 0
        case _:
            raise SystemExit(USAGE)


if __name__ == "__main__":
    sys.exit(main())
