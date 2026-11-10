import frappe
from frappe import _

from textile_mill.reports_lib_ops import late_order_risk


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 140},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
		{"label": _("Line"), "fieldname": "business_line", "fieldtype": "Data", "width": 100},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Due"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 95},
		{"label": _("Days to Due"), "fieldname": "days_to_due", "fieldtype": "Int", "width": 85},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Pending"), "fieldname": "pending_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("In Stock"), "fieldname": "in_stock", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("In Production"), "fieldname": "in_production", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Shortfall"), "fieldname": "shortfall", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Pending Value"), "fieldname": "pending_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 85},
	]
	data = late_order_risk(filters)
	summary = [
		{"label": _("Overdue lines"), "value": len([r for r in data if r.status == 'Overdue']), "datatype": "Int", "indicator": "Red"},
		{"label": _("At-risk lines"), "value": len([r for r in data if r.status == 'At Risk']), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Value at risk"), "value": round(sum(r.pending_value for r in data if r.status != 'On Track'), 2), "datatype": "Currency", "indicator": "Red"},
	]
	return columns, data, None, None, summary
