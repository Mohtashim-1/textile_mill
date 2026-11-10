import frappe
from frappe import _

from textile_mill.reports_lib_ht import set_completion


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Set Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("BOM"), "fieldname": "bom", "fieldtype": "Link", "options": "BOM", "width": 160},
		{"label": _("Sets on Hand"), "fieldname": "on_hand", "fieldtype": "Float", "precision": 0, "width": 105},
		{"label": _("Buildable Sets"), "fieldname": "buildable", "fieldtype": "Int", "width": 110},
		{"label": _("Limiting Component"), "fieldname": "limiting_component", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Open SO Qty"), "fieldname": "open_so_qty", "fieldtype": "Float", "precision": 0, "width": 100},
		{"label": _("Shortfall"), "fieldname": "shortfall", "fieldtype": "Float", "precision": 0, "width": 90},
		{"label": _("Completion %"), "fieldname": "completion_pct", "fieldtype": "Percent", "width": 105},
		{"label": _("Components (available / per set)"), "fieldname": "components", "fieldtype": "Data", "width": 360},
	]
	data = set_completion(filters)
	for r in data:
		r.indicator = "red" if r.shortfall else "green"
	return columns, data
