import frappe
from frappe import _

from textile_mill.reports_lib_ops import order_book_by_line


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Line"), "fieldname": "business_line", "fieldtype": "Data", "width": 100},
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 140},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Due"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 95},
		{"label": _("Days to Due"), "fieldname": "days_to_due", "fieldtype": "Int", "width": 85},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Ordered"), "fieldname": "ordered_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Delivered"), "fieldname": "delivered_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Pending"), "fieldname": "pending_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Pending Value"), "fieldname": "pending_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 85},
	]
	data = order_book_by_line(filters)
	summary = [
		{"label": _("Open lines"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Open order value"), "value": round(sum(r.pending_value for r in data), 2), "datatype": "Currency", "indicator": "Blue"},
	]
	return columns, data, None, None, summary
