# METADATA
# title: worktree_skip
# description: A stopped rebase's commit is dropped only when another named ref preserves it, with its reason.
package runs.worktree_skip

import rego.v1

# METADATA
# title: The skip plan is supplied, never assumed
# custom:
#   code: ERR_SKIP_INPUT_MISSING
deny contains denial if {
	not input.worktree_skip
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no worktree_skip input: an absent plan would read as nothing to refuse",
	}
}

# METADATA
# title: A rebase is in progress
# custom:
#   code: ERR_SKIP_NO_REBASE
deny contains denial if {
	input.worktree_skip.operation != "rebase"
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("no rebase is in progress (operation: %s)", [
			input.worktree_skip.operation,
		]),
	}
}

# METADATA
# title: The rebase stopped on a commit
# custom:
#   code: ERR_SKIP_NO_STOPPED
deny contains denial if {
	input.worktree_skip.operation == "rebase"
	input.worktree_skip.stopped == ""
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "the rebase records no stopped commit, so there is nothing to skip",
	}
}

# METADATA
# title: Another ref preserves the stopped commit
# custom:
#   code: ERR_SKIP_UNPRESERVED
deny contains denial if {
	not input.worktree_skip.preserved
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is not an ancestor of %s, so skipping it would lose it", [
			input.worktree_skip.stopped,
			input.worktree_skip.preserving,
		]),
	}
}

# METADATA
# title: The preserving ref is not the branch being rebased
# custom:
#   code: ERR_SKIP_SAME_BRANCH
deny contains denial if {
	input.worktree_skip.preserving == input.worktree_skip.rebasing
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is the branch being rebased; its ref moves past the commit", [
			input.worktree_skip.rebasing,
		]),
	}
}

# METADATA
# title: A skip says why
# custom:
#   code: ERR_SKIP_NO_REASON
deny contains denial if {
	trim_space(input.worktree_skip.reason) == ""
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "a skip drops a commit from this branch, so it must give its reason",
	}
}
