# tests/test_site_print.py
"""The project site prints its content and nothing covers it (A.281).

A sticky header repeats at the top of every printed page and covers what lies under it. The
print stylesheet is a CSS media query, never a script: it hides every sticky or fixed element and
keeps the provenance and the footer, so a printed page carries its numbers and their source.
"""

from __future__ import annotations

import re
from pathlib import Path

from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site" / "src"
STYLES = SITE / "styles.css"
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
PINNED = re.compile(r"position:\s*(sticky|fixed)")
HIDDEN = re.compile(r"display:\s*none")
PRINT_SCRIPT = re.compile(r"window\.print|beforeprint|matchMedia\(\s*.print")
KEPT = (".provenance", ".foot", "main", "footer")
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _print_block(text: str) -> str:
    start = text.find("@media print")
    assert start >= 0, "the stylesheet has no @media print block"
    opened = text.index("{", start)
    depth = 0
    for index in range(opened, len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            return text[opened + 1 : index]
    raise AssertionError("the @media print block is never closed")


def _selectors(rule: str) -> set[str]:
    return {part.strip() for part in COMMENT.sub("", rule).split(",")}


def _hidden_in_print(text: str) -> set[str]:
    hidden: set[str] = set()
    for selectors, body in RULE.findall(_print_block(text)):
        if HIDDEN.search(body):
            hidden |= _selectors(selectors)
    return hidden


def test_printing_hides_the_sticky_navigation_by_media_query() -> None:
    text = STYLES.read_text(encoding="utf-8")
    hidden = _hidden_in_print(text)
    pinned = {
        selector
        for selectors, body in RULE.findall(text)
        if PINNED.search(body)
        for selector in _selectors(selectors)
    }
    for selector in nonempty(sorted(pinned)):
        assert selector in hidden, (selector, sorted(hidden))
    sources = [*SITE.rglob("*.js"), *SITE.rglob("*.jsx")]
    scripted = sorted(
        str(path.relative_to(ROOT))
        for path in nonempty(sources)
        if PRINT_SCRIPT.search(path.read_text(encoding="utf-8"))
    )
    assert not scripted, scripted


def test_printing_keeps_the_provenance_and_the_footer() -> None:
    hidden = _hidden_in_print(STYLES.read_text(encoding="utf-8"))
    for selector in nonempty(KEPT):
        assert selector not in hidden, (selector, sorted(hidden))
    app = (SITE / "App.jsx").read_text(encoding="utf-8")
    assert '<footer className="foot">' in app, "the footer is not the one this proof keeps"
    provenance = (SITE / "mechanisms" / "Provenance.jsx").read_text(encoding="utf-8")
    assert 'className="provenance"' in provenance, "the provenance is not the one kept"
