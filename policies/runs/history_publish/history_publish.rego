# METADATA
# title: history_publish
# description: A mirror replaces origin's refs only while every recorded tip still holds (A.366).
package runs.history_publish

import rego.v1

# METADATA
# title: The publish plan is supplied, never assumed
# custom:
#   code: ERR_HISTORY_PUBLISH_PLAN_MISSING
deny contains denial if {
	not input.history_publish
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no history_publish input: an absent plan would read as nothing to refuse",
	}
}

# METADATA
# title: No ref moved since the mirror was cut
# custom:
#   code: ERR_HISTORY_PUBLISH_REF_MOVED
deny contains denial if {
	count(input.history_publish.moved) > 0
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("moved since the mirror was cut, so nothing is pushed: %s", [
			concat(", ", input.history_publish.moved),
		]),
	}
}

# METADATA
# title: The mirror holds refs to publish
# custom:
#   code: ERR_HISTORY_PUBLISH_NO_REFS
deny contains denial if {
	count(input.history_publish.refs) == 0
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "the mirror holds no leased branch or tag, so there is nothing to publish",
	}
}

# METADATA
# title: Every branch and tag origin holds is in the mirror
# custom:
#   code: ERR_HISTORY_PUBLISH_REF_UNCOVERED
deny contains denial if {
	count(input.history_publish.uncovered) > 0
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("origin holds refs the mirror lacks, so their history would stay: %s", [
			concat(", ", input.history_publish.uncovered),
		]),
	}
}
