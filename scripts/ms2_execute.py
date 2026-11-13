# scripts/ms2_execute.py
"""ms2:execute -- the Milestone 2 notebook, run in a fresh kernel on verified data (A.329).

The committed notebook carries no outputs. This runs it in batch in a fresh python3 kernel, the
way nbclient executes a notebook, on the MovieLens 1M folder data:fetch verified and published,
and saves the executed copy with its outputs beside the results file the notebook writes.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "milestone2.ipynb"
TABLES = ("ratings.dat", "users.dat", "movies.dat")
# EACH CELL HAS ITS OWN DEADLINE: a million ratings are read and judged in seconds, not minutes.
CELL_SECONDS = 600


def execute(notebook: Path, data: Path, out: Path) -> Path:
    """Run the notebook on data in a fresh kernel; save its executed copy and results into out."""
    missing = [name for name in TABLES if not (data / name).is_file()]
    if missing:
        raise SystemExit(f"ms2:execute: {data} lacks {', '.join(missing)}; run data:fetch first")
    out.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "MS2_DATA": str(data.resolve()),
        "MS2_RESULTS": str((out / "results.json").resolve()),
    }
    source = nbformat.read(notebook, as_version=4)
    where = {"metadata": {"path": str(notebook.parent)}}
    client = NotebookClient(source, kernel_name="python3", timeout=CELL_SECONDS, resources=where)
    client.execute(env=env)
    executed = out / notebook.name
    nbformat.write(source, executed)
    return executed


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit("usage: mise run run ms2:execute <ml-1m folder> <out folder>")
    executed = execute(NOTEBOOK, Path(args[0]), Path(args[1]))
    print(f"ms2:execute: the notebook ran in a fresh kernel and was saved to {executed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
