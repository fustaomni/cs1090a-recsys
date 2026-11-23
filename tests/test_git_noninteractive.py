"""Every git child runs unattended (A.365).

git asks for a missing credential on the terminal itself, so empty stdin does not stop it: a task
that reached an HTTPS remote without credentials waited for a username nobody would type. gitenv
owns what every git child inherits, so it also turns prompting off: GIT_TERMINAL_PROMPT=0 makes
git fail with "terminal prompts disabled", GCM_INTERACTIVE=never does the same for Git Credential
Manager, and an SSH command in BatchMode fails instead of asking for a passphrase or host key. The
remote here is a local server answering 401, standing in for an HTTPS host that wants a login; no
credential helper is consulted, so the only way past the 401 would be a prompt.
"""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import gitenv

# WHAT THE CALLER EXPORTED IS NOT THE PROOF: a shell may already turn prompting off, so each
# proof hands gitenv an environment without these and requires gitenv to set them itself.
PROMPTING = ("GIT_TERMINAL_PROMPT", "GCM_INTERACTIVE", "GIT_SSH_COMMAND", "GIT_ASKPASS")


def _inherited() -> dict[str, str]:
    return {name: value for name, value in os.environ.items() if name not in PROMPTING}


class _Unauthorised(BaseHTTPRequestHandler):
    """Every request is refused for want of a login, as a private HTTPS remote refuses it."""

    def do_GET(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="scratch"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def remote() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Unauthorised)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/scratch.git"
    finally:
        server.shutdown()
        server.server_close()


def test_every_git_child_runs_with_terminal_prompts_disabled() -> None:
    env = gitenv.scrubbed_env(base=_inherited())
    assert env.get("GIT_TERMINAL_PROMPT") == "0"
    assert env.get("GCM_INTERACTIVE") == "never"
    assert "BatchMode=yes" in env.get("GIT_SSH_COMMAND", "")


def test_an_unreachable_https_remote_fails_without_prompting(remote: str) -> None:
    argv = ["git", "-c", "credential.helper=", "ls-remote", remote]
    done = subprocess.run(
        argv,
        env=gitenv.scrubbed_env(base=_inherited()),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert done.returncode != 0
    assert "terminal prompts disabled" in done.stderr
