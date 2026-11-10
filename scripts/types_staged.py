# scripts/types_staged.py
"""types:staged -- the staged Python files, type-checked before the commit (A.267).

PRE-COMMIT'S TYPE CHECK. lefthook passes the staged *.py files and skips the job when there are
none. Only files inside mypy's declared file set are checked, read from pyproject.toml so the set
is declared once; each runs for both platforms, as types does, with mypy's incremental cache, so a
commit's check takes seconds while the full gate, kept at pre-push and in pr, takes minutes.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("darwin", "linux")


def checked(root: Path = ROOT) -> tuple[str, ...]:
    """mypy's file set, as pyproject.toml declares it under [tool.mypy] files."""
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return tuple(config["tool"]["mypy"]["files"])


def staged_python(paths: list[str], root: Path = ROOT) -> list[str]:
    """The staged paths mypy checks: Python files inside its declared file set."""
    tops = checked(root)
    return [path for path in paths if path.endswith(".py") and Path(path).parts[0] in tops]


def command(files: list[str], platform: str) -> list[str]:
    # ONE CACHE PER PLATFORM (A.275): mypy abandons a cache entry written under another platform,
    # so a cache both runs share leaves every run cold; the full types gate uses the same two.
    flags = ["--incremental", "--platform", platform, "--cache-dir", f".mypy_cache/{platform}"]
    return [sys.executable, "-m", "mypy", *flags, *files]


def main(argv: list[str] | None = None) -> int:
    files = staged_python(sys.argv[1:] if argv is None else argv)
    if not files:
        print("no staged Python file in mypy's file set: nothing to type-check")
        return 0
    for platform in PLATFORMS:
        ran = subprocess.run(command(files, platform), cwd=ROOT, check=False)
        if ran.returncode != 0:
            return ran.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
