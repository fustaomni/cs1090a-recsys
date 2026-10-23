# METADATA
# title: worktree_conclude
# description: A merge is concluded only when one is in progress and no marker remains (A.191).
package runs.worktree_conclude

import rego.v1

# METADATA
# title: The conclude plan is supplied, never assumed
# custom:
#   code: ERR_CONCLUDE_INPUT_MISSING
deny contains denial if {
	not input.worktree_conclude
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no worktree_conclude input: an absent plan would read as nothing to refuse",
	}
}

# METADATA
# title: A merge is in progress
# custom:
#   code: ERR_CONCLUDE_NO_MERGE
deny contains denial if {
	input.worktree_conclude.operation != "merge"
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("no merge is in progress (operation: %s)", [input.worktree_conclude.operation]),
	}
}

# METADATA
# title: No conflict marker remains
# custom:
#   code: ERR_CONCLUDE_MARKERS
deny contains denial if {
	some path in input.worktree_conclude.with_markers
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s still holds a conflict marker; resolve it first", [path]),
	}
}
