import frappe
from frappe import _

from textile_mill.reports_lib_ops import operator_performance


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Rank"), "fieldname": "rank", "fieldtype": "Int", "width": 55},
		{"label": _("Operator"), "fieldname": "operator", "fieldtype": "Link", "options": "Employee", "width": 110},
		{"label": _("Operator Name"), "fieldname": "operator_name", "fieldtype": "Data", "width": 140},
		{"label": _("Machine Type"), "fieldname": "machine_type", "fieldtype": "Data", "width": 120},
		{"label": _("Shifts"), "fieldname": "shifts", "fieldtype": "Int", "width": 65},
		{"label": _("Machines"), "fieldname": "machines", "fieldtype": "Int", "width": 75},
		{"label": _("Output"), "fieldname": "output", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Output / Shift"), "fieldname": "output_per_shift", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Efficiency %"), "fieldname": "efficiency_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Faults / Shift"), "fieldname": "faults_per_shift", "fieldtype": "Float", "precision": 2, "width": 105},
		{"label": _("Stop min"), "fieldname": "stop_minutes", "fieldtype": "Int", "width": 75},
	]
	data = operator_performance(filters)
	rows = data[:20]
	chart = {"data": {"labels": [r.operator for r in rows], "datasets": [{"name": _("Efficiency %"), "values": [r.efficiency_pct or 0 for r in rows]}]}, "type": "bar"} if rows else None
	return columns, data, None, chart, None
