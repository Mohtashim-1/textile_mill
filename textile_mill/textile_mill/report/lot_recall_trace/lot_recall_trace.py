import frappe
from frappe import _

from textile_mill.reports_lib_ops import recall_trace


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 170},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 110},
		{"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 150},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Via"), "fieldname": "via", "fieldtype": "Data", "width": 160},
		{"label": _("Depth"), "fieldname": "depth", "fieldtype": "Int", "width": 60},
	]
	data = recall_trace(filters)
	summary = [
		{"label": _("Customers reached"), "value": len({r.customer for r in data}), "datatype": "Int", "indicator": "Red"},
		{"label": _("Shipments"), "value": len({r.voucher_no for r in data}), "datatype": "Int", "indicator": "Orange"},
	]
	return columns, data, None, None, summary
