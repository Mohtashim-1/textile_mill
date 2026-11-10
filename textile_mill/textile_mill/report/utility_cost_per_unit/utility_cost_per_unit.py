import frappe
from frappe import _

from textile_mill.reports_lib_ops import utility_cost_per_unit


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 115},
		{"label": _("Output"), "fieldname": "output_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Absorbed"), "fieldname": "absorbed", "fieldtype": "Currency", "width": 120},
		{"label": _("Actual"), "fieldname": "actual", "fieldtype": "Currency", "width": 120},
		{"label": _("Variance"), "fieldname": "variance", "fieldtype": "Currency", "width": 120},
		{"label": _("Variance %"), "fieldname": "variance_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Absorbed / Unit"), "fieldname": "absorbed_per_unit", "fieldtype": "Currency", "width": 120},
		{"label": _("Actual / Unit"), "fieldname": "actual_per_unit", "fieldtype": "Currency", "width": 120},
	]
	data = utility_cost_per_unit(filters)
	rows = data
	chart = {"data": {"labels": [r.stage for r in rows], "datasets": [{"name": _("Absorbed"), "values": [r.absorbed or 0 for r in rows]}, {"name": _("Actual"), "values": [r.actual or 0 for r in rows]}]}, "type": "bar"} if rows else None
	summary = [
		{"label": _("Actual utilities"), "value": round(sum(r.actual for r in data), 2), "datatype": "Currency", "indicator": "Blue"},
		{"label": _("Actual minus absorbed"), "value": round(sum(r.variance for r in data), 2), "datatype": "Currency", "indicator": "Orange"},
	]
	return columns, data, None, chart, summary
