# METADATA
# title: Founding check of mise.toml before trust
# description: >-
#   Run on the parsed mise.toml before a human grants trust. allow is stated positively:
#   every expected table must equal its intended value, so a missing or extra key leaves
#   it false. violations explains why.
package founding.mise

expected_min_version := data.founding.pins.min_version

expected_tools := data.founding.pins.tools

expected_settings := data.founding.pins.settings

expected_env := data.founding.pins.env

allowed_root := {"min_version", "task_config", "tasks", "tools", "settings", "env"}

allowed_task_keys := {"description", "run", "usage", "raw_args"}

default allow := false

allow if {
	count(violations) == 0
	input.min_version == expected_min_version
	input.tools == expected_tools
	input.settings == expected_settings
	input.env == expected_env
	input.task_config == {"shell": "bash -c"}
	count(input.tasks) > 0
}

violations contains sprintf("root key %q is not allowed", [key]) if {
	some key, _ in input
	not key in allowed_root
}

violations contains sprintf("task %q has key %q outside the allowlist", [name, key]) if {
	some name, task in input.tasks
	some key, _ in task
	not key in allowed_task_keys
}

violations contains sprintf("task %q contains a template", [name]) if {
	some name, task in input.tasks
	some _, value in task
	is_string(value)
	contains(value, "{{")
}
