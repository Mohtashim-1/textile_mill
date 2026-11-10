import frappe
from frappe import _

from textile_mill.reports_lib import utility_variance


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 160},
		{"label": _("Absorbed"), "fieldname": "absorbed", "fieldtype": "Currency", "width": 140},
		{"label": _("Actual"), "fieldname": "actual", "fieldtype": "Currency", "width": 140},
		{"label": _("Variance (Actual − Absorbed)"), "fieldname": "variance", "fieldtype": "Currency", "width": 190},
		{"label": _("Variance %"), "fieldname": "variance_pct", "fieldtype": "Percent", "width": 100},
	]
	data = utility_variance(filters)
	chart = {
		"data": {
			"labels": [r.stage for r in data],
			"datasets": [
				{"name": _("Absorbed"), "values": [round(r.absorbed) for r in data]},
				{"name": _("Actual"), "values": [round(r.actual) for r in data]},
			],
		},
		"type": "bar",
		"colors": ["#1565c0", "#ef6c00"],
	}
	return columns, data, _("Positive variance = under-absorbed utilities (actual above what was charged to production)."), chart
