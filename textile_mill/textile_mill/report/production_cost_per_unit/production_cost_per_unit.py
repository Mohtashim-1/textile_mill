import frappe
from frappe import _

from textile_mill.reports_lib import cost_per_unit, cost_per_unit_by_stage


def execute(filters=None):
	filters = frappe._dict(filters or {})
	cur = {"fieldtype": "Currency", "width": 120}
	columns = [
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 150},
		{"label": _("Stage"), "fieldname": "dm_stage", "fieldtype": "Data", "width": 120},
		{"label": _("Output Item"), "fieldname": "output_item", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Output Qty"), "fieldname": "output_qty", "fieldtype": "Float", "width": 100},
		{"label": _("UOM"), "fieldname": "output_uom", "fieldtype": "Data", "width": 65},
		{"label": _("Material Cost"), "fieldname": "material_cost", **cur},
		{"label": _("Operating Cost"), "fieldname": "operating_cost", **cur},
		{"label": _("Utilities Absorbed"), "fieldname": "utilities_absorbed", **cur},
		{"label": _("Corrective Cost"), "fieldname": "corrective_cost", **cur},
		{"label": _("Scrap Credit"), "fieldname": "scrap_value", **cur},
		{"label": _("Total Actual Cost"), "fieldname": "total_actual_cost", **cur},
		{"label": _("Actual / Unit"), "fieldname": "actual_per_unit", **cur},
		{"label": _("Standard / Unit"), "fieldname": "standard_per_unit", **cur},
		{"label": _("Variance / Unit"), "fieldname": "variance_per_unit", **cur},
		{"label": _("Variance %"), "fieldname": "variance_pct", "fieldtype": "Percent", "width": 95},
	]
	data = cost_per_unit(filters)
	stages = cost_per_unit_by_stage(filters)
	chart = {
		"data": {
			"labels": [s.stage for s in stages],
			"datasets": [
				{"name": _("Actual / Unit"), "values": [round(s.actual_per_unit, 2) for s in stages]},
				{"name": _("Standard / Unit"), "values": [round(s.standard_per_unit, 2) for s in stages]},
			],
		},
		"type": "bar",
		"colors": ["#c62828", "#1565c0"],
	}
	message = _("Standard cost is rolled up from BOM quantities with every input at its own standard, plus BOM operating cost and the stage utility rate.")
	return columns, data, message, chart
