package founding.mise_test

import data.founding.mise

good := {
	"min_version": data.founding.pins.min_version,
	"task_config": {"shell": "bash -c"},
	"tasks": {"test": {"description": "d", "run": "uv run --no-sync pytest"}},
	"tools": data.founding.pins.tools,
	"settings": data.founding.pins.settings,
	"env": data.founding.pins.env,
}

test_intended_config_allowed if mise.allow with input as good

test_missing_min_version_denied if not mise.allow with input as object.remove(good, ["min_version"])

test_missing_settings_denied if not mise.allow with input as object.remove(good, ["settings"])

test_missing_tools_denied if not mise.allow with input as object.remove(good, ["tools"])

test_missing_env_denied if not mise.allow with input as object.remove(good, ["env"])

test_hooks_denied if not mise.allow with input as object.union(good, {"hooks": {"enter": "id"}})

test_env_source_denied if {
	not mise.allow with input as object.union(good, {"env": {"_": {"source": "x.sh"}}})
}

test_trust_setting_denied if {
	not mise.allow with input as object.union(good, {"settings": {"trusted_config_paths": ["/"]}})
}

test_tool_drift_denied if not mise.allow with input as object.union(good, {"tools": {"uv": "0.13.0"}})

test_task_template_denied if {
	not mise.allow with input as object.union(good, {"tasks": {"x": {"run": "{{ exec(command='id') }}"}}})
}

test_task_unknown_key_denied if {
	not mise.allow with input as object.union(good, {"tasks": {"x": {"run": "id", "dir": "/"}}})
}

test_betterleaks_drift_denied if {
	not mise.allow with input as object.union(good, {"tools": {"betterleaks": "2.0.0-rc.2"}})
}
