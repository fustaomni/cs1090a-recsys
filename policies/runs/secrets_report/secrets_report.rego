# policies/runs/secrets_report/secrets_report.rego

# METADATA
# title: secrets_report
# description: No finding in the repository's history, as betterleaks' redacted report names it.
package runs.secrets_report

import rego.v1

# METADATA
# title: The scan is supplied, never assumed
# custom:
#   code: ERR_SECRETS_SCAN_INPUT_MISSING
deny contains denial if {
	not input.secrets_report
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no secrets_report input: an absent scan would read as nothing to refuse",
	}
}

# METADATA
# title: No finding in the repository's history
# custom:
#   code: ERR_SECRETS_FOUND
deny contains denial if {
	some finding in input.secrets_report.findings
	where := $"{finding.file}:{finding.line}"
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": $"{finding.rule_id} at {where}, fingerprint {finding.fingerprint}",
	}
}
