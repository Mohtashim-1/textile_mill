import frappe
from frappe import _

from textile_mill.reports_lib import stage_yield, stage_yield_summary


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Stock Entry"), "fieldname": "stock_entry", "fieldtype": "Link", "options": "Stock Entry", "width": 150},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 150},
		{"label": _("Stage"), "fieldname": "dm_stage", "fieldtype": "Data", "width": 120},
		{"label": _("Output Item"), "fieldname": "output_item", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Output Qty"), "fieldname": "output_qty", "fieldtype": "Float", "width": 105},
		{"label": _("UOM"), "fieldname": "output_uom", "fieldtype": "Data", "width": 65},
		{"label": _("Main Input Qty"), "fieldname": "input_qty", "fieldtype": "Float", "width": 115},
		{"label": _("Input UOM"), "fieldname": "input_uoms", "fieldtype": "Data", "width": 75},
		{"label": _("Scrap Qty"), "fieldname": "scrap_qty", "fieldtype": "Float", "width": 95},
		{"label": _("Loss Qty"), "fieldname": "loss_qty", "fieldtype": "Float", "width": 95},
		{"label": _("Yield %"), "fieldname": "yield_pct", "fieldtype": "Percent", "width": 85},
		{"label": _("Waste %"), "fieldname": "waste_pct", "fieldtype": "Percent", "width": 85},
		{"label": _("Loss %"), "fieldname": "loss_pct", "fieldtype": "Percent", "width": 80},
		{"label": _("Output per Input Unit"), "fieldname": "output_per_input", "fieldtype": "Float", "precision": 3, "width": 120},
	]
	data = stage_yield(filters)
	summary = [s for s in stage_yield_summary(filters) if s.yield_pct is not None]
	chart = {
		"data": {"labels": [s.stage for s in summary], "datasets": [{"name": _("Yield %"), "values": [round(s.yield_pct, 1) for s in summary]}]},
		"type": "bar",
		"colors": ["#2e7d32"],
	}
	return columns, data, None, chart
