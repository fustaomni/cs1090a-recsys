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

# METADATA
# title: The archive is the one its reviewed pin names
# custom:
#   code: ERR_DATA_PIN_MISMATCH
deny contains denial if {
	fetch := input.data_fetch
	fetch.archive_sha256 != fetch.archive_pinned
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("archive SHA-256 %s, reviewed pin %s", [fetch.archive_sha256, fetch.archive_pinned]),
	}
}

# METADATA
# title: Every member is a plain file or folder inside the archive
# custom:
#   code: ERR_DATA_MEMBER_UNSAFE
deny contains denial if {
	fetch := input.data_fetch
	some name in fetch.unsafe
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is absolute, climbs out, names a drive, or is not a plain file", [name]),
	}
}

over_limit(fetch) if fetch.member_count > fetch.max_members

over_limit(fetch) if fetch.total_bytes > fetch.max_total_bytes

# METADATA
# title: The archive is within its member and size limits
# custom:
#   code: ERR_DATA_ARCHIVE_OVER_LIMIT
deny contains denial if {
	fetch := input.data_fetch
	over_limit(fetch)
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf(
			"%d members of at most %d, %d bytes of at most %d",
			[fetch.member_count, fetch.max_members, fetch.total_bytes, fetch.max_total_bytes],
		),
	}
}
