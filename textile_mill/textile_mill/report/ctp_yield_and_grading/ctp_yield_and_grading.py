from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from textile_mill.reports_lib_ht import ctp_entries


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("CTP Entry"), "fieldname": "ctp_production_entry", "fieldtype": "Link", "options": "CTP Production Entry", "width": 130},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Product"), "fieldname": "product_item", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Line"), "fieldname": "line", "fieldtype": "Link", "options": "Workstation", "width": 100},
		{"label": _("Fabric Issued"), "fieldname": "fabric_issued", "fieldtype": "Float", "width": 105},
		{"label": _("Planned"), "fieldname": "pieces_planned", "fieldtype": "Int", "width": 80},
		{"label": _("Cut"), "fieldname": "pieces_cut", "fieldtype": "Int", "width": 75},
		{"label": _("A Grade"), "fieldname": "pieces_a", "fieldtype": "Int", "width": 80},
		{"label": _("Seconds"), "fieldname": "pieces_seconds", "fieldtype": "Int", "width": 80},
		{"label": _("Seconds kg"), "fieldname": "seconds_weight_kg", "fieldtype": "Float", "width": 90},
		{"label": _("Rags kg"), "fieldname": "rags_kg", "fieldtype": "Float", "width": 80},
		{"label": _("Cutting Waste kg"), "fieldname": "cutting_waste_kg", "fieldtype": "Float", "width": 115},
		{"label": _("CTP Yield %"), "fieldname": "ctp_yield_pct", "fieldtype": "Percent", "width": 95},
		{"label": _("Seconds %"), "fieldname": "seconds_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Weight Check"), "fieldname": "weight_check", "fieldtype": "Link", "options": "Piece Weight Check", "width": 120},
	]
	data = ctp_entries(filters)
	by_product = defaultdict(lambda: [0, 0])
	for r in data:
		by_product[r.product_item][0] += r.pieces_a or 0
		by_product[r.product_item][1] += r.pieces_planned or 0
	chart = {
		"data": {
			"labels": list(by_product),
			"datasets": [{"name": _("CTP Yield %"), "values": [round(flt(a) / p * 100, 2) if p else 0 for a, p in by_product.values()]}],
		},
		"type": "bar",
		"colors": ["#00897b"],
	}
	planned = sum(r.pieces_planned or 0 for r in data)
	cut = sum(r.pieces_cut or 0 for r in data)
	summary = [
		{"label": _("A-grade pieces"), "value": sum(r.pieces_a or 0 for r in data), "datatype": "Int", "indicator": "Green"},
		{"label": _("CTP Yield %"), "value": round(sum(r.pieces_a or 0 for r in data) / planned * 100, 2) if planned else 0,
			"datatype": "Percent", "indicator": "Blue"},
		{"label": _("Seconds %"), "value": round(sum(r.pieces_seconds or 0 for r in data) / cut * 100, 2) if cut else 0,
			"datatype": "Percent", "indicator": "Orange"},
	]
	return columns, data, None, chart, summary
