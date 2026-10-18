# METADATA
# title: upstream_copies
# description: An untracked copy of an upstream is removed only when it matches the pinned tree.
package runs.upstream_copies

import rego.v1

# METADATA
# title: The copy inventory is supplied, never assumed
# custom:
#   code: ERR_COPIES_INPUT_MISSING
deny contains denial if {
	not input.upstream_copies
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no copy inventory: an absent one would read as nothing left to verify",
	}
}

# METADATA
# title: Every untracked copy matches the pinned tree
# custom:
#   code: ERR_COPIES_UNVERIFIED
deny contains denial if {
	some copy in input.upstream_copies.copies
	copy.local_blob != copy.upstream_blob
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s does not match the pinned tree; it is kept", [copy.path]),
	}
}
