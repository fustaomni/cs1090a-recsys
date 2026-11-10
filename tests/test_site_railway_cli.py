# tests/test_site_railway_cli.py
"""The Railway CLI runs from the site's locked install, never through npx (A.273).

npx falls back to the public registry when node_modules is missing and runs whatever package
claims the name; here the name railway belongs to Railway's IaC SDK, not to @railway/cli, whose
binary it is. An npm script resolves only node_modules/.bin, and every task installs first.
"""

from __future__ import annotations

import ast
import shlex
import tomllib
from pathlib import Path

import site_deployed
from nonvacuous import nonempty

ROOT = Path(__file__).resolve().parent.parent
CLI = "npm run --silent railway"
INSTALLED = ("mise run site:install", "mise run site:build")
LINK = "mise run site:link"
LINKED = ("site:status", "site:config-pull", "site:config-plan")
SEPARATORS = frozenset({"&&", "||", ";", "|", "&"})


def _runs() -> dict[str, str]:
    """Every mise task's run text, by task name."""
    config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
    return {name: str(task.get("run", "")) for name, task in config["tasks"].items()}


def _shell_runs_npx_railway(run: str) -> bool:
    """A shell run invokes railway through npx, read as shlex tokens: comments are not code."""
    if "npx" not in run:
        return False
    lexer = shlex.shlex(run, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    command: list[str] = []
    for word in lexer:
        if word in SEPARATORS:
            command = []
            continue
        command.append(word)
        if word == "railway" and "npx" in command:
            return True
    return False


def _python_runs_npx_railway(source: str) -> bool:
    """A Python command names npx then railway, read as AST string constants, never comments."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Tuple | ast.List):
            words = [
                item.value
                for item in node.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]
            if "npx" in words and "railway" in words[words.index("npx") :]:
                return True
    return False


def test_no_task_runs_the_railway_cli_through_npx() -> None:
    found = [f"mise.toml {name}" for name, run in _runs().items() if _shell_runs_npx_railway(run)]
    for path in nonempty(sorted((ROOT / "scripts").glob("*.py"))):
        if _python_runs_npx_railway(path.read_text(encoding="utf-8")):
            found.append(str(path.relative_to(ROOT)))
    assert found == [], found


def test_every_railway_task_installs_the_locked_site_first() -> None:
    cli = sorted((name, run) for name, run in _runs().items() if CLI in run)
    for name, run in nonempty(cli):
        before = run[: run.index(CLI)]
        assert any(step in before for step in INSTALLED), (name, run)


def test_every_linked_task_links_the_declared_service_first() -> None:
    """A task that reads a directory's link first links this checkout to the declared ids."""
    runs = _runs()
    assert runs["site:link"].endswith("scripts/site_record.py link"), runs["site:link"]
    for name in nonempty(LINKED):
        run = runs[name]
        assert LINK in run and run.index(LINK) < run.index(CLI), (name, run)
    # THE IDENTITY IS BUILT BY ITS OWN MODEL: a generated project carries no
    # contracts/site-railway.toml (copier.yml), and the model's rules name every field required.
    identity = site_deployed.Identity(project="p", environment="e", service="s", domain="d")
    expected = [
        "link",
        "--project",
        identity.project,
        "--environment",
        identity.environment,
        "--service",
        identity.service,
    ]
    command = site_deployed.link_command(identity)
    assert command[-len(expected) :] == expected, command
