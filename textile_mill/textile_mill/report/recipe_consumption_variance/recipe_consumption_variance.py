import frappe
from frappe import _

from textile_mill.reports_lib import recipe_variance

HIGHLIGHT_PCT = 5


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 150},
		{"label": _("Dye Recipe"), "fieldname": "dye_recipe", "fieldtype": "Link", "options": "Dye Recipe", "width": 120},
		{"label": _("Chemical"), "fieldname": "item_code", "fieldtype": "Data", "width": 120},
		{"label": _("Base Consumed (kg)"), "fieldname": "base_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Recipe g/kg"), "fieldname": "recipe_g_per_kg", "fieldtype": "Float", "width": 95},
		{"label": _("Standard Qty (kg)"), "fieldname": "standard_qty", "fieldtype": "Float", "precision": 3, "width": 120},
		{"label": _("Actual Qty (kg)"), "fieldname": "actual_qty", "fieldtype": "Float", "precision": 3, "width": 115},
		{"label": _("Actual g/kg"), "fieldname": "actual_g_per_kg", "fieldtype": "Float", "precision": 2, "width": 95},
		{"label": _("Variance Qty"), "fieldname": "variance_qty", "fieldtype": "Float", "precision": 3, "width": 105},
		{"label": _("Variance %"), "fieldname": "variance_pct", "fieldtype": "Percent", "width": 95},
		{"label": _("Variance Amount"), "fieldname": "variance_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Over Limit"), "fieldname": "over_limit", "fieldtype": "Check", "width": 80},
	]
	data = [
		dict(r, over_limit=1 if (r.get("variance_pct") or 0) > HIGHLIGHT_PCT else 0)
		for r in recipe_variance(filters)
		if not filters.get("dm_stage") or r.get("is_total") or r.get("stage") == filters.dm_stage
	]
	return columns, data, _("Rows over {0}% variance are flagged.").format(HIGHLIGHT_PCT)
