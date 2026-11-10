import frappe
from frappe import _

from textile_mill.reports_lib_ops import corrective_cost_summary


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 115},
		{"label": _("Workstation"), "fieldname": "workstation", "fieldtype": "Link", "options": "Workstation", "width": 120},
		{"label": _("Operation"), "fieldname": "operation", "fieldtype": "Link", "options": "Operation", "width": 170},
		{"label": _("Jobs"), "fieldname": "jobs", "fieldtype": "Int", "width": 60},
		{"label": _("Work Orders"), "fieldname": "work_orders", "fieldtype": "Int", "width": 90},
		{"label": _("Hours"), "fieldname": "hours", "fieldtype": "Float", "precision": 2, "width": 80},
		{"label": _("Cost"), "fieldname": "cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Re-dye % (stage)"), "fieldname": "redye_pct", "fieldtype": "Percent", "width": 110},
		{"label": _("Reasons"), "fieldname": "reasons", "fieldtype": "Data", "width": 240},
	]
	data = corrective_cost_summary(filters)
	rows = data
	chart = {"data": {"labels": [r.operation for r in rows], "datasets": [{"name": _("Cost"), "values": [r.cost or 0 for r in rows]}]}, "type": "bar"} if rows else None
	summary = [
		{"label": _("Corrective jobs"), "value": sum(r.jobs for r in data), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Corrective cost"), "value": round(sum(r.cost for r in data), 2), "datatype": "Currency", "indicator": "Red"},
	]
	return columns, data, None, chart, summary
