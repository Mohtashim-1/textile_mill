import frappe
from frappe import _

from textile_mill.reports_lib_ht import weight_checks


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Weight Check"), "fieldname": "piece_weight_check", "fieldtype": "Link", "options": "Piece Weight Check", "width": 125},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 135},
		{"label": _("Target kg"), "fieldname": "target_weight_kg", "fieldtype": "Float", "precision": 3, "width": 85},
		{"label": _("Avg kg"), "fieldname": "avg_weight_kg", "fieldtype": "Float", "precision": 4, "width": 85},
		{"label": _("Variance %"), "fieldname": "variance_pct", "fieldtype": "Float", "precision": 2, "width": 90},
		{"label": _("CV %"), "fieldname": "cv_pct", "fieldtype": "Float", "precision": 2, "width": 70},
		{"label": _("Implied GSM"), "fieldname": "implied_gsm", "fieldtype": "Float", "precision": 1, "width": 95},
		{"label": _("Result"), "fieldname": "result", "fieldtype": "Data", "width": 95},
		{"label": _("Pieces"), "fieldname": "pieces", "fieldtype": "Float", "precision": 0, "width": 80},
		{"label": _("Cotton Give-away kg"), "fieldname": "giveaway_kg", "fieldtype": "Float", "precision": 2, "width": 135},
		{"label": _("Give-away Value"), "fieldname": "giveaway_value", "fieldtype": "Currency", "width": 120},
	]
	data = weight_checks(filters)
	chart = {
		"data": {
			"labels": [r.item_code for r in data],
			"datasets": [
				{"name": _("Target kg"), "values": [r.target_weight_kg for r in data]},
				{"name": _("Avg kg"), "values": [r.avg_weight_kg for r in data]},
			],
		},
		"type": "bar",
		"colors": ["#9e9e9e", "#1e88e5"],
	}
	summary = [
		{"label": _("Cotton give-away kg"), "value": round(sum(r.giveaway_kg for r in data), 2), "datatype": "Float",
			"indicator": "Orange"},
		{"label": _("Give-away value"), "value": round(sum(r.giveaway_value for r in data), 2), "datatype": "Currency",
			"indicator": "Red"},
	]
	return columns, data, None, chart, summary
