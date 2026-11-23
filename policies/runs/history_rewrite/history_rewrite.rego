# METADATA
# title: history_rewrite
# description: A history rewrite writes only into a new mirror, and only by rules (A.364).
package runs.history_rewrite

import rego.v1

# METADATA
# title: The rewrite plan is supplied, never assumed
# custom:
#   code: ERR_REWRITE_PLAN_MISSING
deny contains denial if {
	not input.history_rewrite
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no history_rewrite input: an absent plan would read as nothing to refuse",
	}
}

# METADATA
# title: The mirror is a new path, never an existing repository
# custom:
#   code: ERR_REWRITE_TARGET_EXISTS
deny contains denial if {
	input.history_rewrite.mirror_exists
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s already exists: a rewrite writes only into a new mirror", [
			input.history_rewrite.mirror,
		]),
	}
}

# METADATA
# title: The rules change something
# custom:
#   code: ERR_REWRITE_NO_RULES
deny contains denial if {
	input.history_rewrite.rules == 0
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "the rules name no line to drop, no text to replace and no cited path",
	}
}
