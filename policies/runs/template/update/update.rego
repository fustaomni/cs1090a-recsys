# policies/runs/template/update/update.rego

# METADATA
# title: Template update policy
# description: A generated project takes a later commit of this template, pinned, clean, on a branch.
# entrypoint: true
package runs.template.update

# An ACTION policy, as runs.template.new is: template:update builds the request and asks in the
# same call, so every rule first requires the request, and the repository gate judges nothing
# here (A.134).

import rego.v1

_protected := {"main", "develop", "HEAD"}

# METADATA
# title: The destination was generated
# description: Copier updates only a project it generated, from the answers it recorded.
# custom:
#   code: ERR_TEMPLATE_UPDATE_NOT_GENERATED
deny contains denial if {
	input.template_update
	not input.template_update.answers_present
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s holds no .copier-answers.yml", [input.template_update.destination]),
	}
}

# METADATA
# title: The ref is a full commit sha
# description: A branch, a tag or a short sha lets Copier choose, and a bare update has destroyed a project.
# custom:
#   code: ERR_TEMPLATE_UPDATE_UNPINNED
deny contains denial if {
	input.template_update
	not regex.match(`^[0-9a-f]{40}$`, input.template_update.ref)
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is not a full commit sha, so Copier would choose", [input.template_update.ref]),
	}
}

# METADATA
# title: The project was generated from this template
# description: Its recorded _src_path must be the repository this template declares.
# custom:
#   code: ERR_TEMPLATE_UPDATE_FOREIGN
deny contains denial if {
	request := input.template_update
	request.source != request.template
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s records another template: %v", [request.destination, request.source]),
	}
}

# METADATA
# title: The project's tree is clean
# description: Copier refuses to update a dirty tree, and a three-way merge needs a committed base.
# custom:
#   code: ERR_TEMPLATE_UPDATE_DIRTY
deny contains denial if {
	input.template_update
	not input.template_update.clean
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s has uncommitted changes", [input.template_update.destination]),
	}
}

# METADATA
# title: The update lands on a feature branch
# description: Never main, develop or a detached HEAD; it reaches develop through a pull request.
# custom:
#   code: ERR_TEMPLATE_UPDATE_PROTECTED
deny contains denial if {
	request := input.template_update
	request.branch in _protected
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s is on %s, not a feature branch", [request.destination, request.branch]),
	}
}

# METADATA
# title: The project is not already at the ref
# description: Copier records an abbreviated sha, so a ref starting with it is the recorded commit.
# custom:
#   code: ERR_TEMPLATE_UPDATE_CURRENT
deny contains denial if {
	request := input.template_update
	is_string(request.recorded)
	startswith(request.ref, request.recorded)
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": sprintf("%s already records %s", [request.destination, request.recorded]),
	}
}

# METADATA
# title: The template:update request is present
# description: Without it no rule above judges anything, and an empty judgement reads as a pass.
# custom:
#   code: ERR_TEMPLATE_UPDATE_INPUT_MISSING
deny contains denial if {
	not input.template_update
	denial := {
		"code": rego.metadata.rule().custom.code,
		"message": "no template_update was supplied, so no rule judged the request",
	}
}
