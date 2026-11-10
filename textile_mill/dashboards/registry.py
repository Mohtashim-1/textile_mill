"""Dashboard registry: who may open which dashboard and which module builds it (Part C §2)."""

import frappe
from frappe import _

ALL_DIRECTORS = ("CEO", "Board Viewer", "System Manager")

DASHBOARDS: dict[str, dict] = {
	"command-center": {
		"title": "Command Center",
		"module": "textile_mill.dashboards.widgets.command_center",
		"roles": ALL_DIRECTORS + ("CFO", "Production Director", "Plant Controller"),
		"refresh": 300,
	},
	"production": {
		"title": "Production & Efficiency",
		"module": "textile_mill.dashboards.widgets.production",
		"roles": ALL_DIRECTORS + ("Production Director", "Plant Controller", "Manufacturing Manager"),
		"refresh": 300,
	},
	"finance": {
		"title": "Cost & Finance",
		"module": "textile_mill.dashboards.widgets.finance",
		"roles": ALL_DIRECTORS + ("CFO", "Plant Controller", "Accounts Manager"),
		"refresh": 900,
	},
	"quality-inventory": {
		"title": "Quality & Inventory",
		"module": "textile_mill.dashboards.widgets.quality_inventory",
		"roles": ALL_DIRECTORS + ("Production Director", "Plant Controller", "Stock Manager", "Quality Manager", "Finishing QA User"),
		"refresh": 300,
	},
	"sales": {
		"title": "Sales & Orders",
		"module": "textile_mill.dashboards.widgets.sales",
		"roles": ALL_DIRECTORS + ("CFO", "Sales Manager"),
		"refresh": 900,
	},
	"procurement": {
		"title": "Procurement & Suppliers",
		"module": "textile_mill.dashboards.widgets.procurement",
		"roles": ALL_DIRECTORS + ("CFO", "Purchase Manager", "Plant Controller"),
		"refresh": 900,
	},
	"stage": {
		"title": "Stage Drill-down",
		"module": "textile_mill.dashboards.widgets.stage",
		"roles": ALL_DIRECTORS + ("Production Director", "Plant Controller", "Manufacturing Manager", "Recycling User",
			"Spinning User", "Dyeing User", "Indigo User", "Weaving User", "Finishing QA User", "Garment User"),
		"refresh": 300,
	},
}


def get(dashboard: str) -> dict:
	if dashboard not in DASHBOARDS:
		frappe.throw(_("Unknown dashboard {0}").format(dashboard))
	return DASHBOARDS[dashboard]


def can_view(dashboard: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)) & set(get(dashboard)["roles"]))


def check(dashboard: str) -> dict:
	config = get(dashboard)
	if not can_view(dashboard):
		frappe.throw(_("You are not permitted to view the {0} dashboard.").format(_(config["title"])), frappe.PermissionError)
	return config


def visible_dashboards(user: str | None = None) -> list[dict]:
	return [{"name": k, "title": v["title"]} for k, v in DASHBOARDS.items() if can_view(k, user)]
