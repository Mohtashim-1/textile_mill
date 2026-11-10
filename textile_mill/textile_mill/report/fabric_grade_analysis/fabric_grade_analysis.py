import frappe
from frappe import _

from textile_mill.reports_lib import fabric_grades, grade_split


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Inspection"), "fieldname": "fabric_roll_inspection", "fieldtype": "Link", "options": "Fabric Roll Inspection", "width": 130},
		{"label": _("Date"), "fieldname": "inspection_date", "fieldtype": "Date", "width": 95},
		{"label": _("Lot Batch"), "fieldname": "lot_batch", "fieldtype": "Link", "options": "Batch", "width": 120},
		{"label": _("Rolls"), "fieldname": "rolls", "fieldtype": "Int", "width": 70},
		{"label": _("Meters"), "fieldname": "meters", "fieldtype": "Float", "width": 95},
		{"label": _("A (m)"), "fieldname": "a_m", "fieldtype": "Float", "width": 90},
		{"label": _("A %"), "fieldname": "a_pct", "fieldtype": "Percent", "width": 75},
		{"label": _("B (m)"), "fieldname": "b_m", "fieldtype": "Float", "width": 85},
		{"label": _("B %"), "fieldname": "b_pct", "fieldtype": "Percent", "width": 70},
		{"label": _("Rejected (m)"), "fieldname": "rejected_m", "fieldtype": "Float", "width": 100},
		{"label": _("Rejected %"), "fieldname": "rejected_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Avg Points / 100 sq yd"), "fieldname": "avg_points", "fieldtype": "Float", "precision": 1, "width": 140},
		{"label": _("Top Defects"), "fieldname": "top_defects", "fieldtype": "Data", "width": 220},
	]
	data = fabric_grades(filters)
	split = grade_split(filters)
	chart = {
		"data": {"labels": ["A", "B", _("Rejected")], "datasets": [{"name": _("Meters"), "values": [round(split[g], 1) for g in ("A", "B", "Rejected")]}]},
		"type": "donut",
		"colors": ["#2e7d32", "#f9a825", "#c62828"],
	}
	return columns, data, None, chart
