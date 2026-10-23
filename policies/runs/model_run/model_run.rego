# METADATA
# title: model_run
# description: A fit is used only if it read what was declared, before the validation cutoff.
package runs.model_run

import rego.v1

# METADATA
# title: The fit record is supplied, never assumed
# custom:
#   code: ERR_MODEL_INPUT_MISSING
deny contains denial if {
	not input.model_run
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no model_run input: an absent record would read as a fit allowed",
	}
}

# METADATA
# title: A fit reads only rows before the validation cutoff
# custom:
#   code: ERR_MODEL_FIT_PAST_CUTOFF
deny contains denial if {
	run := input.model_run
	run.last_training_time >= run.validation_cutoff_time
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("trained up to time %d, at or after the cutoff %d", [run.last_training_time, run.validation_cutoff_time]),
	}
}

# METADATA
# title: A fit reads only declared features
# custom:
#   code: ERR_MODEL_FEATURE_UNDECLARED
deny contains denial if {
	run := input.model_run
	declared := {feature.name | some feature in run.declared.features}
	some feature in run.features
	not feature.name in declared
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("feature %s is not declared", [feature.name]),
	}
}

# METADATA
# title: Every feature uses only data from before each row's time
# custom:
#   code: ERR_MODEL_FEATURE_NOT_POINT_IN_TIME
deny contains denial if {
	run := input.model_run
	some feature in run.features
	not feature.point_in_time
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("feature %s can read ratings after its own row", [feature.name]),
	}
}

# METADATA
# title: A fit reads exactly the declared data
# custom:
#   code: ERR_MODEL_DATA_UNDECLARED
deny contains denial if {
	run := input.model_run
	run.data_sha256 != run.declared.data_sha256
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("read data %s, declared %s", [run.data_sha256, run.declared.data_sha256]),
	}
}
