import frappe
from frappe import _

from textile_mill.reports_lib_ops import chemical_consumption


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 115},
		{"label": _("Chemical"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("Consumed"), "fieldname": "qty", "fieldtype": "Float", "precision": 3, "width": 95},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Value"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Stage Output"), "fieldname": "stage_output", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Output UOM"), "fieldname": "output_uom", "fieldtype": "Data", "width": 85},
		{"label": _("Qty per 1,000 Output"), "fieldname": "qty_per_1000", "fieldtype": "Float", "precision": 3, "width": 140},
		{"label": _("Cost / Output Unit"), "fieldname": "cost_per_unit", "fieldtype": "Currency", "width": 120},
	]
	data = chemical_consumption(filters)
	summary = [
		{"label": _("Chemical value"), "value": round(sum(r.amount for r in data), 2), "datatype": "Currency", "indicator": "Blue"},
	]
	return columns, data, None, None, summary
