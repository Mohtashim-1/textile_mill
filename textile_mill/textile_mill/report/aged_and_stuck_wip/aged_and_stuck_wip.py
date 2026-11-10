import frappe
from frappe import _

from textile_mill.reports_lib_ops import aged_wip


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 115},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 170},
		{"label": _("Status"), "fieldname": "inventory_status", "fieldtype": "Data", "width": 85},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Value"), "fieldname": "value", "fieldtype": "Currency", "width": 120},
		{"label": _("Age (days)"), "fieldname": "age_days", "fieldtype": "Int", "width": 85},
		{"label": _("Age Bucket"), "fieldname": "age_bucket", "fieldtype": "Data", "width": 90},
	]
	data = aged_wip(filters)
	summary = [
		{"label": _("Batches"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Value"), "value": round(sum(r.value for r in data), 2), "datatype": "Currency", "indicator": "Orange"},
	]
	return columns, data, None, None, summary
