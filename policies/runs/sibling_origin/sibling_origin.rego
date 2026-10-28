# METADATA
# title: sibling_origin
# description: A sibling's origin is set to its declared source only when it names the same repository.
package runs.sibling_origin

import rego.v1

# METADATA
# title: The origin request is supplied, never assumed
# custom:
#   code: ERR_SIBLING_ORIGIN_INPUT_MISSING
deny contains denial if {
	not input.sibling_origin
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no sibling_origin input: an absent observation would read as one allowed",
	}
}

# METADATA
# title: The sibling is already cloned
# custom:
#   code: ERR_SIBLING_ORIGIN_NO_CLONE
deny contains denial if {
	evidence := input.sibling_origin
	not evidence.clone_exists
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is not a clone yet; sibling:checkout makes it first", [evidence.clone]),
	}
}

# METADATA
# title: Only the transport may change, never the repository
# custom:
#   code: ERR_SIBLING_ORIGIN_FOREIGN
deny contains denial if {
	evidence := input.sibling_origin
	evidence.clone_exists
	not evidence.same_repository
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s: origin %s is another repository", [evidence.clone, evidence.configured]),
	}
}
