import frappe
from frappe import _

from textile_mill.reports_lib_ops import downtime_mtbf


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Workstation"), "fieldname": "workstation", "fieldtype": "Link", "options": "Workstation", "width": 120},
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 115},
		{"label": _("Stops"), "fieldname": "stops", "fieldtype": "Int", "width": 65},
		{"label": _("Downtime h"), "fieldname": "downtime_hours", "fieldtype": "Float", "precision": 2, "width": 95},
		{"label": _("Run h"), "fieldname": "run_hours", "fieldtype": "Float", "precision": 2, "width": 85},
		{"label": _("Availability %"), "fieldname": "availability_pct", "fieldtype": "Percent", "width": 105},
		{"label": _("MTBF h"), "fieldname": "mtbf_hours", "fieldtype": "Float", "precision": 2, "width": 85},
		{"label": _("MTTR h"), "fieldname": "mttr_hours", "fieldtype": "Float", "precision": 2, "width": 85},
		{"label": _("Top Reason"), "fieldname": "top_reason", "fieldtype": "Data", "width": 180},
	]
	data = downtime_mtbf(filters)
	rows = data[:15]
	chart = {"data": {"labels": [r.workstation for r in rows], "datasets": [{"name": _("Downtime h"), "values": [r.downtime_hours or 0 for r in rows]}]}, "type": "bar"} if rows else None
	summary = [
		{"label": _("Downtime hours"), "value": round(sum(r.downtime_hours for r in data), 1), "datatype": "Float", "indicator": "Red"},
		{"label": _("Stops"), "value": sum(r.stops for r in data), "datatype": "Int", "indicator": "Orange"},
	]
	return columns, data, None, chart, summary
