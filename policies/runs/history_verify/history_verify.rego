# METADATA
# title: history_verify
# description: A rewritten mirror is accepted only when its rules find nothing left (A.364).
package runs.history_verify

import rego.v1

# METADATA
# title: The rewrite report is supplied, never assumed
# custom:
#   code: ERR_REWRITE_REPORT_MISSING
deny contains denial if {
	not input.history_verify
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no history_verify input: an absent report would read as a clean rewrite",
	}
}

# METADATA
# title: Nothing the rules match remains
# custom:
#   code: ERR_REWRITE_MATCHES_REMAIN
deny contains denial if {
	input.history_verify.remaining_matches > 0
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%d match(es) of the rules remain in the mirror", [
			input.history_verify.remaining_matches,
		]),
	}
}

# METADATA
# title: No cited commit id names a rewritten commit
# custom:
#   code: ERR_REWRITE_CITATIONS_STALE
deny contains denial if {
	input.history_verify.stale_citations > 0
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%d cited id(s) still name a rewritten commit", [
			input.history_verify.stale_citations,
		]),
	}
}

# METADATA
# title: The mirror has no remote to push to
# custom:
#   code: ERR_REWRITE_REMOTE_LEFT
deny contains denial if {
	input.history_verify.remotes > 0
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("the mirror keeps %d remote(s): a rewrite never pushes", [
			input.history_verify.remotes,
		]),
	}
}
