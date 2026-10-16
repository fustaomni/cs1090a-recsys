# METADATA
# title: branch_push
# description: A branch is pushed only to its own ref, never a protected one, after the gate.
package runs.branch_push

import rego.v1

# METADATA
# title: The push request is supplied, never assumed
# custom:
#   code: ERR_PUSH_INPUT_MISSING
deny contains denial if {
	not input.branch_push
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no branch_push input: an absent request would read as a push allowed",
	}
}

# METADATA
# title: A detached head is never pushed
# custom:
#   code: ERR_PUSH_DETACHED
deny contains denial if {
	request := input.branch_push
	request.branch == null
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "HEAD is detached: there is no branch to push",
	}
}

# METADATA
# title: A protected branch changes only through a merged pull request
# custom:
#   code: ERR_PUSH_PROTECTED_BRANCH
deny contains denial if {
	request := input.branch_push
	request.protected
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is protected: it changes only through a merged pull request", [request.remote_ref]),
	}
}

# METADATA
# title: The full gate passed at the commit being pushed
# custom:
#   code: ERR_PUSH_GATE_UNPROVEN
deny contains denial if {
	request := input.branch_push
	not request.gate_passed_at_head
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("no passing check is recorded at %s", [request.head]),
	}
}
