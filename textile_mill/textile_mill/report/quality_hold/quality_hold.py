import frappe
from frappe import _

from textile_mill.reports_lib_ops import quality_hold


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Hold Type"), "fieldname": "hold_type", "fieldtype": "Data", "width": 110},
		{"label": _("Document Type"), "fieldname": "reference_doctype", "fieldtype": "Data", "width": 120},
		{"label": _("Document"), "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 160},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 115},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 140},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("Value"), "fieldname": "value", "fieldtype": "Currency", "width": 120},
		{"label": _("Age (days)"), "fieldname": "age_days", "fieldtype": "Int", "width": 85},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
	]
	data = quality_hold(filters)
	summary = [
		{"label": _("Awaiting QI"), "value": len([r for r in data if r.hold_type == 'Awaiting QI']), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Rejected QIs"), "value": len([r for r in data if r.hold_type == 'Rejected QI']), "datatype": "Int", "indicator": "Red"},
		{"label": _("Held stock value"), "value": round(sum(r.value or 0 for r in data if r.hold_type == 'Held Stock'), 2), "datatype": "Currency", "indicator": "Red"},
	]
	return columns, data, None, None, summary
