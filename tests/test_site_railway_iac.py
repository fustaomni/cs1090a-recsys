# tests/test_site_railway_iac.py
"""The site's Railway service is Infrastructure as Code, with no Config as Code left (A.268).

Railway stops reading railway.json and railway.toml on 2026-12-01. The service is declared in
site/.railway/railway.ts (A.98), and with no Config File path set on the service, deleting
railway.json is the cutover itself. The restart policy stays undeclared on purpose: Railway's
default is stored as null, so declaring it is a diff no apply can close.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IAC = ROOT / "site" / ".railway" / "railway.ts"


def _code(path: Path) -> str:
    """The file's code, its comment lines dropped, so an explanation can never satisfy a check."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("//"))


def test_the_service_is_declared_as_infrastructure_as_code() -> None:
    code = _code(IAC)
    assert "defineRailway(" in code, code
    assert "service(" in code, code
    assert 'builder: "RAILPACK"' in code, code
    assert "restartPolicy" not in code, code


def test_no_config_as_code_file_remains() -> None:
    """Nothing a commit would carry is present: tracked or new, and on disk (A.262's set)."""
    patterns = ("railway.json", "railway.toml", "**/railway.json", "**/railway.toml")
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", *patterns],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    present = [path for path in listed if (ROOT / path).is_file()]
    assert present == [], present
