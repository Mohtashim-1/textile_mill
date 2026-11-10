import frappe
from frappe import _

from textile_mill.reports_lib_ops import material_shortage


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("Group"), "fieldname": "item_group", "fieldtype": "Data", "width": 120},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("To Issue"), "fieldname": "required_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Free Stock"), "fieldname": "in_stock", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("On Order (PO)"), "fieldname": "on_order", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Short Now"), "fieldname": "short_now", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Shortage after PO"), "fieldname": "shortage", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Work Orders"), "fieldname": "work_orders", "fieldtype": "Int", "width": 90},
		{"label": _("First Need"), "fieldname": "first_need", "fieldtype": "Date", "width": 95},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
	]
	data = material_shortage(filters)
	summary = [
		{"label": _("Items short"), "value": len([r for r in data if r.status == 'Short']), "datatype": "Int", "indicator": "Red"},
		{"label": _("Covered by open POs"), "value": len([r for r in data if r.status == 'Covered by PO']), "datatype": "Int", "indicator": "Orange"},
	]
	return columns, data, None, None, summary
