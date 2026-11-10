import frappe
from frappe import _

from textile_mill.reports_lib_ops import yield_exceptions


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 115},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Input"), "fieldname": "input_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Output"), "fieldname": "output_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Yield %"), "fieldname": "yield_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Target %"), "fieldname": "target_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Gap pts"), "fieldname": "gap_pct", "fieldtype": "Float", "precision": 2, "width": 80},
		{"label": _("Loss vs Target"), "fieldname": "loss_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Loss Value"), "fieldname": "loss_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 80},
	]
	data = yield_exceptions(filters)
	rows = data
	chart = {"data": {"labels": [r.work_order for r in rows], "datasets": [{"name": _("Loss Value"), "values": [r.loss_value or 0 for r in rows]}]}, "type": "bar"} if rows else None
	summary = [
		{"label": _("Work orders below target"), "value": len([r for r in data if r.gap_pct > 0]), "datatype": "Int", "indicator": "Red"},
		{"label": _("Loss value vs target"), "value": round(sum(r.loss_value for r in data), 2), "datatype": "Currency", "indicator": "Red"},
	]
	return columns, data, None, chart, summary
