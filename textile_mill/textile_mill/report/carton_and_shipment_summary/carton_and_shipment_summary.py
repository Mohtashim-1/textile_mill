import frappe
from frappe import _

from textile_mill.reports_lib_ht import shipments


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 140},
		{"label": _("PO No"), "fieldname": "po_no", "fieldtype": "Data", "width": 110},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Packing Lists"), "fieldname": "packing_lists", "fieldtype": "Int", "width": 100},
		{"label": _("Cartons"), "fieldname": "cartons", "fieldtype": "Int", "width": 80},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "precision": 0, "width": 80},
		{"label": _("Net kg"), "fieldname": "net_kg", "fieldtype": "Float", "precision": 1, "width": 90},
		{"label": _("Gross kg"), "fieldname": "gross_kg", "fieldtype": "Float", "precision": 1, "width": 90},
		{"label": _("CBM"), "fieldname": "cbm", "fieldtype": "Float", "precision": 3, "width": 80},
		{"label": _("Cartons Shipped"), "fieldname": "cartons_shipped", "fieldtype": "Int", "width": 115},
		{"label": _("Shipped On"), "fieldname": "shipped_on", "fieldtype": "Date", "width": 95},
		{"label": _("Delivery Notes"), "fieldname": "delivery_notes", "fieldtype": "Data", "width": 170},
	]
	data = shipments(filters)
	chart = {
		"data": {
			"labels": [r.sales_order for r in data],
			"datasets": [{"name": _("CBM"), "values": [round(r.cbm or 0, 2) for r in data]}],
		},
		"type": "bar",
		"colors": ["#5e35b1"],
	}
	return columns, data, None, chart
