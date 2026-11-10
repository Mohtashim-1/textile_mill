import frappe
from frappe import _

from textile_mill.reports_lib_ops import dye_house_log


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 115},
		{"label": _("Machine"), "fieldname": "workstation", "fieldtype": "Link", "options": "Workstation", "width": 90},
		{"label": _("Recipe"), "fieldname": "dye_recipe", "fieldtype": "Link", "options": "Dye Recipe", "width": 120},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Input"), "fieldname": "input_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Output"), "fieldname": "output_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Yield %"), "fieldname": "yield_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Chemical Cost"), "fieldname": "chemical_cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Chem Cost / Unit"), "fieldname": "chemical_cost_per_unit", "fieldtype": "Currency", "width": 120},
		{"label": _("Machine Load %"), "fieldname": "machine_load_pct", "fieldtype": "Percent", "width": 110},
		{"label": _("Re-dyed"), "fieldname": "redyed", "fieldtype": "Check", "width": 75},
	]
	data = dye_house_log(filters)
	summary = [
		{"label": _("Batches"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Re-dyed"), "value": sum(r.redyed for r in data), "datatype": "Int", "indicator": "Red"},
		{"label": _("Chemical cost"), "value": round(sum(r.chemical_cost for r in data), 2), "datatype": "Currency", "indicator": "Blue"},
	]
	return columns, data, None, None, summary
