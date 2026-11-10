import frappe
from frappe import _

from textile_mill.reports_lib_ops import defect_pareto


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Defect"), "fieldname": "defect_type", "fieldtype": "Link", "options": "Fabric Defect Type", "width": 140},
		{"label": _("Occurrences"), "fieldname": "occurrences", "fieldtype": "Int", "width": 95},
		{"label": _("Rolls"), "fieldname": "rolls", "fieldtype": "Int", "width": 65},
		{"label": _("Points"), "fieldname": "points", "fieldtype": "Float", "precision": 0, "width": 80},
		{"label": _("Share %"), "fieldname": "share_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Cumulative %"), "fieldname": "cumulative_pct", "fieldtype": "Percent", "width": 105},
		{"label": _("Vital Few"), "fieldname": "vital_few", "fieldtype": "Check", "width": 75},
	]
	data = defect_pareto(filters)
	rows = data
	chart = {"data": {"labels": [r.defect_type for r in rows], "datasets": [{"name": _("Points"), "values": [r.points or 0 for r in rows]}]}, "type": "bar"} if rows else None
	summary = [
		{"label": _("Total points"), "value": sum(r.points for r in data), "datatype": "Float", "indicator": "Orange"},
		{"label": _("Vital-few defects"), "value": sum(r.vital_few for r in data), "datatype": "Int", "indicator": "Red"},
	]
	return columns, data, None, chart, summary
