import frappe
from frappe import _

from textile_mill.reports_lib_ops import marker_efficiency


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Cut Plan"), "fieldname": "name", "fieldtype": "Link", "options": "Cut Plan", "width": 125},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 140},
		{"label": _("Style"), "fieldname": "style_template", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Fabric"), "fieldname": "fabric_item", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("UOM"), "fieldname": "fabric_uom", "fieldtype": "Data", "width": 60},
		{"label": _("Marker m"), "fieldname": "marker_length_m", "fieldtype": "Float", "precision": 2, "width": 85},
		{"label": _("Plies"), "fieldname": "plies", "fieldtype": "Int", "width": 60},
		{"label": _("Pcs / Marker"), "fieldname": "pieces_per_marker", "fieldtype": "Int", "width": 90},
		{"label": _("Pieces Cut"), "fieldname": "total_pieces", "fieldtype": "Int", "width": 85},
		{"label": _("Ordered"), "fieldname": "ordered_pieces", "fieldtype": "Float", "precision": 0, "width": 85},
		{"label": _("Over-cut"), "fieldname": "over_cut", "fieldtype": "Float", "precision": 0, "width": 80},
		{"label": _("Over-cut %"), "fieldname": "over_cut_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Fabric Issued"), "fieldname": "fabric_issued_m", "fieldtype": "Float", "precision": 2, "width": 105},
		{"label": _("Standard Fabric"), "fieldname": "standard_fabric_m", "fieldtype": "Float", "precision": 2, "width": 115},
		{"label": _("Fabric / Piece"), "fieldname": "fabric_per_piece", "fieldtype": "Float", "precision": 4, "width": 100},
		{"label": _("Cutting Var %"), "fieldname": "cutting_variance_pct", "fieldtype": "Percent", "width": 100},
		{"label": _("End-bit %"), "fieldname": "end_bit_allowance_pct", "fieldtype": "Percent", "width": 90},
	]
	data = marker_efficiency(filters)
	return columns, data, None, None, None
