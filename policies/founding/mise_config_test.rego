package founding.mise_test

import data.founding.mise

good := {
	"min_version": "2026.10.4",
	"task_config": {"shell": "bash -c"},
	"tasks": {"test": {"description": "d", "run": "uv run --no-sync pytest"}},
	"tools": {"betterleaks": "1.9.0", "lefthook": "2.2.0", "opa": "1.21.1", "regal": "0.43.0", "uv": "0.12.23"},
	"settings": {"lockfile": true, "minimum_release_age": "2026-10-08T00:00:00Z"},
	"env": {"UV_CACHE_DIR": "{{config_root}}/.cache/uv"},
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
