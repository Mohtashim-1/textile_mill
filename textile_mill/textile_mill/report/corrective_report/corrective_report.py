import frappe
from frappe import _

from textile_mill.reports_lib import corrective_jobs, redye_pct_by_stage


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Job Card"), "fieldname": "job_card", "fieldtype": "Link", "options": "Job Card", "width": 130},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Stage"), "fieldname": "dm_stage", "fieldtype": "Data", "width": 120},
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 150},
		{"label": _("Corrective Operation"), "fieldname": "operation", "fieldtype": "Link", "options": "Operation", "width": 170},
		{"label": _("For Operation"), "fieldname": "for_operation", "fieldtype": "Link", "options": "Operation", "width": 150},
		{"label": _("Workstation"), "fieldname": "workstation", "fieldtype": "Link", "options": "Workstation", "width": 110},
		{"label": _("Hours"), "fieldname": "hours", "fieldtype": "Float", "precision": 2, "width": 75},
		{"label": _("Hour Rate"), "fieldname": "hour_rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Cost"), "fieldname": "cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Reason"), "fieldname": "reason", "fieldtype": "Data", "width": 220},
	]
	data = corrective_jobs(filters)
	redye = redye_pct_by_stage(filters)
	summary = [
		{"label": _("Re-process % ({0})").format(stage), "value": round(pct, 1), "datatype": "Percent", "indicator": "Orange" if pct else "Green"}
		for stage, pct in redye.items()
		if pct
	]
	summary.insert(0, {"label": _("Corrective Cost"), "value": sum(r.cost or 0 for r in data), "datatype": "Currency", "indicator": "Red"})
	return columns, data, None, None, summary
