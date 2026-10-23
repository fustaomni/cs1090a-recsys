# METADATA
# title: worktree_abort
# description: A stopped rebase or merge is aborted only when one is in progress (A.191).
package runs.worktree_abort

import rego.v1

# METADATA
# title: The abort plan is supplied, never assumed
# custom:
#   code: ERR_ABORT_INPUT_MISSING
deny contains denial if {
	not input.worktree_abort
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no worktree_abort input: an absent plan would read as nothing to refuse",
	}
}

# METADATA
# title: A rebase or merge is in progress
# custom:
#   code: ERR_ABORT_NOTHING_IN_PROGRESS
deny contains denial if {
	input.worktree_abort.operation == "none"
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no rebase or merge is in progress, so there is nothing to abort",
	}
}
