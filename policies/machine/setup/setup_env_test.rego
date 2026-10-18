# policies/machine/setup/setup_env_test.rego
package machine.setup_test

import rego.v1

import data.machine.setup

test_an_unobserved_environment_is_refused if {
    denials := setup.deny with input as {}
    some denial in denials
    denial.code == "ERR_SETUP_ENV_UNOBSERVED"
}

test_an_inherited_variable_is_refused if {
    observed := {"selecting_variables": ["UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV"], "present": ["VIRTUAL_ENV"]}
    denials := setup.deny with input as {"setup_environment": observed}
    some denial in denials
    denial.code == "ERR_SETUP_ENV_INHERITED"
}

test_a_clean_environment_is_allowed if {
    observed := {"selecting_variables": ["UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV"], "present": []}
    denials := setup.deny with input as {"setup_environment": observed}
    count(denials) == 0
}
