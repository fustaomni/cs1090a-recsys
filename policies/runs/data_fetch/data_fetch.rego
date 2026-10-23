# METADATA
# title: data_fetch
# description: Data is unpacked only when its published checksum and required files are proven.
package runs.data_fetch

import rego.v1

# METADATA
# title: The fetch record is supplied, never assumed
# custom:
#   code: ERR_DATA_INPUT_MISSING
deny contains denial if {
	not input.data_fetch
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no data_fetch input: an absent record would read as data allowed",
	}
}

# METADATA
# title: The archive matches the checksum its publisher published
# custom:
#   code: ERR_DATA_CHECKSUM_MISMATCH
deny contains denial if {
	fetch := input.data_fetch
	fetch.md5_published != fetch.md5_observed
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("published MD5 %v, archive MD5 %s", [fetch.md5_published, fetch.md5_observed]),
	}
}

# METADATA
# title: Every required file is in the archive
# custom:
#   code: ERR_DATA_FILES_MISSING
deny contains denial if {
	fetch := input.data_fetch
	present := {entry.name | some entry in fetch.files}
	some name in fetch.required
	not name in present
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is missing from the archive", [name]),
	}
}
