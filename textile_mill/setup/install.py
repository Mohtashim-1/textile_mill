"""Install / migrate hooks: roles, custom fields, workflow, settings defaults."""

import frappe

from textile_mill.constants import ROLES, SETTINGS_DEFAULTS


def after_install() -> None:
	setup()


def after_migrate() -> None:
	setup()


def setup() -> None:
	"""Idempotent: safe to run on every migrate."""
	from textile_mill.setup.custom_fields import setup_custom_fields
	from textile_mill.setup.workflow import setup_workflow

	create_roles()
	setup_custom_fields()
	setup_workflow()
	set_property_setters()
	set_settings_defaults()
	add_indexes()


def set_property_setters() -> None:
	"""Each stage runs its own Work Order, so sub-assembly operations must not be exploded into it."""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	make_property_setter(
		"Work Order", "use_multi_level_bom", "default", "0", "Check", validate_fields_for_doctype=False, is_system_generated=False
	)


def create_roles() -> None:
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def set_settings_defaults() -> None:
	"""Fill settings that have never been stored; values the user changed (including 0) are left alone."""
	singles = frappe.qb.Table("tabSingles")
	stored = set(
		frappe.qb.from_(singles).select(singles.field).where(singles.doctype == "Textile Mill Settings").run(pluck=True)
	)
	missing = {k: v for k, v in SETTINGS_DEFAULTS.items() if k not in stored}
	if not missing:
		return
	settings = frappe.get_single("Textile Mill Settings")
	settings.update(missing)
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)


def add_indexes() -> None:
	"""Dashboard query indexes (Part C §4.3)."""
	frappe.db.add_index("Stock Entry", ["dm_stage", "posting_date"], "dm_stage_posting_date")
	frappe.db.add_index("Work Order", ["dm_stage", "status", "planned_start_date"], "dm_stage_status_start")
	frappe.db.add_index("KPI Daily Snapshot", ["snapshot_date", "kpi", "stage"], "snapshot_kpi_stage")
