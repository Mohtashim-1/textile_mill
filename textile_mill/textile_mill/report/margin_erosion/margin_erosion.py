import frappe
from frappe import _

from textile_mill.reports_lib_ops import margin_erosion


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 140},
		{"label": _("Stage"), "fieldname": "dm_stage", "fieldtype": "Data", "width": 115},
		{"label": _("Item"), "fieldname": "output_item", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Output"), "fieldname": "output_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("UOM"), "fieldname": "output_uom", "fieldtype": "Data", "width": 60},
		{"label": _("Std Cost / Unit"), "fieldname": "standard_per_unit", "fieldtype": "Currency", "width": 120},
		{"label": _("Actual / Unit"), "fieldname": "actual_per_unit", "fieldtype": "Currency", "width": 120},
		{"label": _("Over Std %"), "fieldname": "variance_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Excess Cost"), "fieldname": "excess_cost", "fieldtype": "Currency", "width": 120},
	]
	data = margin_erosion(filters)
	rows = data
	chart = {"data": {"labels": [r.work_order for r in rows], "datasets": [{"name": _("Excess Cost"), "values": [r.excess_cost or 0 for r in rows]}]}, "type": "bar"} if rows else None
	summary = [
		{"label": _("Work orders over standard"), "value": len(data), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Excess cost"), "value": round(sum(r.excess_cost for r in data), 2), "datatype": "Currency", "indicator": "Red"},
	]
	return columns, data, None, chart, summary
