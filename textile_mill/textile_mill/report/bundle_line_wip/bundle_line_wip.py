import frappe
from frappe import _

from textile_mill.reports_lib_ops import bundle_wip


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Cut Plan"), "fieldname": "cut_plan", "fieldtype": "Link", "options": "Cut Plan", "width": 125},
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
		{"label": _("Variant"), "fieldname": "variant_item", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Size"), "fieldname": "size", "fieldtype": "Data", "width": 60},
		{"label": _("Line"), "fieldname": "stitch_line", "fieldtype": "Link", "options": "Workstation", "width": 80},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Bundles"), "fieldname": "bundles", "fieldtype": "Int", "width": 75},
		{"label": _("Pieces"), "fieldname": "pieces", "fieldtype": "Float", "precision": 0, "width": 80},
		{"label": _("Cut On"), "fieldname": "oldest", "fieldtype": "Date", "width": 95},
		{"label": _("Last Stitched"), "fieldname": "last_stitched", "fieldtype": "Datetime", "width": 150},
		{"label": _("Age (days)"), "fieldname": "age_days", "fieldtype": "Int", "width": 85},
	]
	data = bundle_wip(filters)
	summary = [
		{"label": _("Bundles open"), "value": sum(r.bundles for r in data if r.status not in ('Stitched', 'Rejected')), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Pieces stitched"), "value": sum(r.pieces for r in data if r.status == 'Stitched'), "datatype": "Float", "indicator": "Green"},
	]
	return columns, data, None, None, summary
