import frappe
from frappe import _

from textile_mill.reports_lib import genealogy


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Node"), "fieldname": "node_type", "fieldtype": "Data", "width": 160},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 190},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 65},
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 120},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Supplier / Customer"), "fieldname": "party", "fieldtype": "Data", "width": 200},
	]
	if not (filters.get("batch_no") or filters.get("work_order") or filters.get("delivery_note")):
		return columns, [], _("Select a Batch, a garment Work Order or a Delivery Note.")
	return columns, genealogy(filters)
