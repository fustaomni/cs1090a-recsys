# METADATA
# title: plan_resolve
# description: Plan files are resolved only while a merge or rebase has stopped on one of them.
package runs.plan_resolve

import rego.v1

# METADATA
# title: The resolve plan is supplied, never assumed
# custom:
#   code: ERR_PLAN_RESOLVE_INPUT_MISSING
deny contains denial if {
	not input.plan_resolve
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no plan_resolve input: an absent plan would read as nothing to refuse",
	}
}

# METADATA
# title: A merge or a rebase is in progress
# custom:
#   code: ERR_PLAN_RESOLVE_NO_OPERATION
deny contains denial if {
	input.plan_resolve.operation == "none"
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no merge or rebase is in progress, so no plan file can be in conflict",
	}
}

# METADATA
# title: A plan file is in conflict
# custom:
#   code: ERR_PLAN_RESOLVE_NOTHING_CONFLICTED
deny contains denial if {
	input.plan_resolve.operation != "none"
	count(input.plan_resolve.conflicted) == 0
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": $"the {input.plan_resolve.operation} in progress holds no conflicted plan file",
	}
}
