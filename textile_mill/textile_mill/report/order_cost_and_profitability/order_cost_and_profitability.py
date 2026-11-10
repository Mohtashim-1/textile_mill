import frappe
from frappe import _

from textile_mill.reports_lib import order_profitability


def execute(filters=None):
	filters = frappe._dict(filters or {})
	cur = {"fieldtype": "Currency", "width": 115}
	columns = [
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Fabric / pc"), "fieldname": "fabric_per_pc", **cur},
		{"label": _("Trims / pc"), "fieldname": "trims_per_pc", **cur},
		{"label": _("CMT / pc"), "fieldname": "cmt_per_pc", **cur},
		{"label": _("Unwashed / pc"), "fieldname": "unwashed_per_pc", **cur},
		{"label": _("Washing / pc"), "fieldname": "washing_per_pc", **cur},
		{"label": _("Washed / pc"), "fieldname": "washed_per_pc", **cur},
	]
	if not filters.get("sales_order"):
		return columns, []
	p = order_profitability(filters.sales_order)
	summary = [
		{"label": _("Revenue"), "value": p.revenue, "datatype": "Currency", "indicator": "Blue"},
		{"label": _("COGS"), "value": p.cogs, "datatype": "Currency", "indicator": "Orange"},
		{"label": _("Gross Margin"), "value": p.gross_margin, "datatype": "Currency", "indicator": "Green" if p.gross_margin >= 0 else "Red"},
		{"label": _("Margin %"), "value": round(p.margin_pct, 1), "datatype": "Percent", "indicator": "Green" if p.gross_margin >= 0 else "Red"},
	]
	message = None if p.build_up else _("No garment cost build-up: this order is not linked to a Cut Plan.")
	return columns, p.build_up, message, None, summary
