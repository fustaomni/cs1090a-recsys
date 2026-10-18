# policies/machine/environment/environment_test.rego
package machine.environment_test

import rego.v1

import data.machine.environment

test_an_unobserved_sync_is_refused if {
    denials := environment.deny with input as {}
    some denial in denials
    denial.code == "ERR_ENV_UNOBSERVED"
}

test_a_changed_lock_left_uninstalled_is_refused if {
    synced := {"lock_changed": true, "installed": false, "install_exit_code": 1}
    denials := environment.deny with input as {"environment_sync": synced}
    some denial in denials
    denial.code == "ERR_ENV_STALE"
}

test_an_installed_lock_is_allowed if {
    synced := {"lock_changed": true, "installed": true, "install_exit_code": 0}
    denials := environment.deny with input as {"environment_sync": synced}
    count(denials) == 0
}
