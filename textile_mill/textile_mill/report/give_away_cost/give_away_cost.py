import frappe
from frappe import _

from textile_mill.reports_lib_ops import giveaway_cost


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Checks"), "fieldname": "checks", "fieldtype": "Int", "width": 70},
		{"label": _("Failed"), "fieldname": "failed", "fieldtype": "Int", "width": 70},
		{"label": _("Pieces"), "fieldname": "pieces", "fieldtype": "Float", "precision": 0, "width": 90},
		{"label": _("Target kg"), "fieldname": "target_weight_kg", "fieldtype": "Float", "precision": 3, "width": 85},
		{"label": _("Avg Variance %"), "fieldname": "avg_variance_pct", "fieldtype": "Percent", "width": 110},
		{"label": _("Give-away kg"), "fieldname": "giveaway_kg", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Give-away Value"), "fieldname": "giveaway_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Per 1,000 pcs"), "fieldname": "giveaway_per_1000", "fieldtype": "Currency", "width": 120},
	]
	data = giveaway_cost(filters)
	rows = data
	chart = {"data": {"labels": [r.item_code for r in rows], "datasets": [{"name": _("Give-away Value"), "values": [r.giveaway_value or 0 for r in rows]}]}, "type": "bar"} if rows else None
	summary = [
		{"label": _("Give-away kg"), "value": round(sum(r.giveaway_kg for r in data), 2), "datatype": "Float", "indicator": "Orange"},
		{"label": _("Give-away value"), "value": round(sum(r.giveaway_value for r in data), 2), "datatype": "Currency", "indicator": "Red"},
	]
	return columns, data, None, chart, summary
