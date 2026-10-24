# METADATA
# title: sibling_trust
# description: A sibling's configuration is trusted only unmodified at a commit on its develop.
package runs.sibling_trust

import rego.v1

# METADATA
# title: The sibling's trust evidence is supplied, never assumed
# custom:
#   code: ERR_SIBLING_TRUST_INPUT_MISSING
deny contains denial if {
	not input.sibling_trust
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no sibling_trust input: an absent observation would read as one trusted",
	}
}

# METADATA
# title: The sibling's HEAD is a commit on its develop
# custom:
#   code: ERR_SIBLING_HEAD_NOT_ON_DEVELOP
deny contains denial if {
	evidence := input.sibling_trust
	not evidence.head_on_develop
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is checked out at a commit not on its develop", [evidence.name]),
	}
}

# METADATA
# title: The sibling's mise.toml is unmodified
# custom:
#   code: ERR_SIBLING_CONFIG_MODIFIED
deny contains denial if {
	evidence := input.sibling_trust
	not evidence.config_unmodified
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s's mise.toml differs from the commit it is at", [evidence.name]),
	}
}

# METADATA
# title: The sibling's override is exactly the declared FAS mode
# custom:
#   code: ERR_SIBLING_OVERRIDE_MISMATCH
deny contains denial if {
	evidence := input.sibling_trust
	not evidence.override_matches
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s's mise.local.toml is not the declared FAS mode", [evidence.name]),
	}
}

# METADATA
# title: The sibling's flake.lock still pins the nixpkgs its FAS mode was read from
# custom:
#   code: ERR_SIBLING_TOOLCHAIN_STALE
deny contains denial if {
	evidence := input.sibling_trust
	not evidence.toolchain_current
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s's flake.lock moved past its pins' nixpkgs; run sibling:pin %s", [evidence.name, evidence.name]),
	}
}
