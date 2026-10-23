# METADATA
# title: sibling_override
# description: A sibling's FAS mode is rewritten only in an existing clone of its declared source.
package runs.sibling_override

import rego.v1

# METADATA
# title: The override request is supplied, never assumed
# custom:
#   code: ERR_SIBLING_OVERRIDE_INPUT_MISSING
deny contains denial if {
	not input.sibling_override
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no sibling_override input: an absent observation would read as one allowed",
	}
}

# METADATA
# title: The sibling is already cloned
# custom:
#   code: ERR_SIBLING_OVERRIDE_NO_CLONE
deny contains denial if {
	evidence := input.sibling_override
	not evidence.clone_exists
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is not a clone yet; sibling:checkout makes it first", [evidence.clone]),
	}
}

# METADATA
# title: The clone's origin is the declared source
# custom:
#   code: ERR_SIBLING_OVERRIDE_FOREIGN
deny contains denial if {
	evidence := input.sibling_override
	evidence.clone_exists
	not evidence.origin_matches
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s was cloned from %s, not the declared source", [evidence.clone, evidence.origin]),
	}
}
