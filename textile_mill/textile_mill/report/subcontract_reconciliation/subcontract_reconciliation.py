import frappe
from frappe import _

from textile_mill.reports_lib_ops import subcontract_reconciliation


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Subcontracting Order"), "fieldname": "subcontracting_order", "fieldtype": "Link", "options": "Subcontracting Order", "width": 150},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 130},
		{"label": _("Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 95},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Line"), "fieldname": "line_type", "fieldtype": "Data", "width": 110},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Ordered / Required"), "fieldname": "ordered_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Received"), "fieldname": "received_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Pending"), "fieldname": "pending_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Sent"), "fieldname": "supplied_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Consumed"), "fieldname": "consumed_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Returned"), "fieldname": "returned_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("With Supplier"), "fieldname": "balance_with_supplier", "fieldtype": "Float", "precision": 2, "width": 105},
	]
	data = subcontract_reconciliation(filters)
	summary = [
		{"label": _("FG pending"), "value": round(sum(r.pending_qty or 0 for r in data), 2), "datatype": "Float", "indicator": "Orange"},
		{"label": _("Material still with supplier"), "value": round(sum(r.balance_with_supplier or 0 for r in data), 2), "datatype": "Float", "indicator": "Red"},
	]
	return columns, data, None, None, summary
