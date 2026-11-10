import frappe
from frappe import _

from textile_mill.reports_lib_ops import waste_recovery


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Waste Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Stages"), "fieldname": "stages", "fieldtype": "Data", "width": 180},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Generated"), "fieldname": "generated_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Book Value"), "fieldname": "book_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Sold"), "fieldname": "sold_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Sales Value"), "fieldname": "sales_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Unsold"), "fieldname": "unsold_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Sold %"), "fieldname": "sold_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Realised Rate"), "fieldname": "realised_rate", "fieldtype": "Currency", "width": 120},
	]
	data = waste_recovery(filters)
	summary = [
		{"label": _("Waste generated"), "value": round(sum(r.generated_qty for r in data), 1), "datatype": "Float", "indicator": "Orange"},
		{"label": _("Recovered (sales)"), "value": round(sum(r.sales_value for r in data), 2), "datatype": "Currency", "indicator": "Green"},
	]
	return columns, data, None, None, summary
