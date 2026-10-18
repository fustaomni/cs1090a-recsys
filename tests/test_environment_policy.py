"""machine.environment refuses an unobserved sync and a changed lock left uninstalled (A.93)."""

from __future__ import annotations

from env_sync import EnvironmentSync, environment_denials
from opa import denials


def test_an_unobserved_sync_is_refused() -> None:
    found = denials("data.machine.environment.deny", {})
    assert any(d.startswith("[ERR_ENV_UNOBSERVED]") for d in found), found


def test_a_changed_lock_left_uninstalled_is_refused() -> None:
    broken = EnvironmentSync(lock_changed=True, installed=False, install_exit_code=1)
    assert any(d.startswith("[ERR_ENV_STALE]") for d in environment_denials(broken))
    healthy = EnvironmentSync(lock_changed=True, installed=True, install_exit_code=0)
    assert environment_denials(healthy) == []
