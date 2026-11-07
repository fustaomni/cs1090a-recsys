# METADATA
# title: status_paths
# description: The paths a commit should name come from git's own answer, never from silence.
package runs.status_paths

import rego.v1

# METADATA
# title: The status observation is supplied, never assumed
# custom:
#   code: ERR_STATUS_PATHS_INPUT_MISSING
deny contains denial if {
	not input.status_paths
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no status_paths input: an absent observation would read as nothing changed",
	}
}

# METADATA
# title: A git that could not answer is never read as a clean tree
# custom:
#   code: ERR_STATUS_PATHS_UNANSWERED
deny contains denial if {
	input.status_paths.answered == false
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": $"git could not report the changes: {input.status_paths.detail}",
	}
}
