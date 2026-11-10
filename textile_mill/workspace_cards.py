"""Methods behind the "Textile Mill" workspace number cards (Part B §10)."""

import json

import frappe
from frappe.utils import add_days, flt, today

from textile_mill import reports_lib as rl
from textile_mill.utils import get_settings

DEFAULT_PERIOD_DAYS = 90


def _filters(filters) -> dict:
	if isinstance(filters, str):
		filters = json.loads(filters or "{}")
	f = dict(filters or {})
	f.setdefault("company", frappe.defaults.get_user_default("Company"))
	f.setdefault("to_date", today())
	f.setdefault("from_date", add_days(f["to_date"], -DEFAULT_PERIOD_DAYS))
	return f


def _percent(value) -> dict:
	return {"value": flt(value, 1), "fieldtype": "Percent"}


def _currency(value, company) -> dict:
	return {"value": flt(value, 2), "fieldtype": "Currency", "options": frappe.get_cached_value("Company", company, "default_currency")}


def _stage_yield(filters, stage: str) -> float:
	row = next((r for r in rl.stage_yield_summary(filters) if r.stage == stage), None)
	return row.yield_pct if row and row.yield_pct is not None else 0


@frappe.whitelist()
def recovery_yield(filters=None):
	return _percent(_stage_yield(_filters(filters), "Cotton Recycling"))


@frappe.whitelist()
def spinning_yield(filters=None):
	return _percent(_stage_yield(_filters(filters), "Spinning"))


@frappe.whitelist()
def indigo_g_per_kg(filters=None):
	rows = [r for r in rl.recipe_variance(_filters(filters)) if r.get("item_code") == "CHM-IND"]
	base = sum(flt(r.base_qty) for r in rows)
	actual = sum(flt(r.actual_qty) for r in rows)
	return {"value": flt(actual / base * 1000, 1) if base else 0, "fieldtype": "Float"}


@frappe.whitelist()
def loom_efficiency(filters=None):
	return _percent(rl.weighted_loom_efficiency({"loom_type": "Air-jet Denim", **_filters(filters)}))


@frappe.whitelist()
def a_grade_pct(filters=None):
	return _percent(rl.grade_split(_filters(filters))["A_pct"])


@frappe.whitelist()
def cost_per_meter_a(filters=None):
	f = _filters(filters)
	graded = [r.graded_item for r in get_settings().grade_items if r.grade == "A"]
	row = frappe.db.sql(
		"""select sum(d.amount), sum(d.transfer_qty) from `tabStock Entry Detail` d join `tabStock Entry` se on se.name = d.parent
		where se.docstatus = 1 and se.purpose = 'Repack' and se.company = %(company)s and ifnull(d.t_warehouse, '') != ''
		and se.posting_date between %(from_date)s and %(to_date)s and d.item_code in %(items)s""",
		{**f, "items": tuple(graded) or ("",)},
	)[0]
	return _currency(flt(row[0]) / flt(row[1]) if flt(row[1]) else 0, f["company"])


@frappe.whitelist()
def cutting_variance_pct(filters=None):
	f = _filters(filters)
	row = frappe.db.sql(
		"""select sum(c.cutting_variance_m), sum(c.standard_fabric_m) from `tabCut Plan` c join `tabItem` i on i.name = c.style_template
		where c.docstatus = 1 and i.dm_stage = 'Garments' and c.company = %(company)s
		and c.posting_date between %(from_date)s and %(to_date)s""",
		f,
	)[0]
	return _percent(flt(row[0]) / flt(row[1]) * 100 if flt(row[1]) else 0)


@frappe.whitelist()
def wip_value(filters=None):
	f = _filters(filters)
	return _currency(rl.wip_value(f["company"]), f["company"])
