import frappe
from frappe import _

from textile_mill.reports_lib_ops import shift_register


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Shift"), "fieldname": "shift", "fieldtype": "Link", "options": "Mill Shift", "width": 60},
		{"label": _("Sheet Type"), "fieldname": "reference_doctype", "fieldtype": "Data", "width": 10},
		{"label": _("Shift Sheet"), "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 130},
		{"label": _("Machine Type"), "fieldname": "machine_type", "fieldtype": "Data", "width": 120},
		{"label": _("Machine"), "fieldname": "machine", "fieldtype": "Link", "options": "Workstation", "width": 90},
		{"label": _("Operator"), "fieldname": "operator", "fieldtype": "Link", "options": "Employee", "width": 110},
		{"label": _("Operator Name"), "fieldname": "operator_name", "fieldtype": "Data", "width": 130},
		{"label": _("Output"), "fieldname": "output", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 60},
		{"label": _("Efficiency %"), "fieldname": "efficiency_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Breaks / Defects"), "fieldname": "faults", "fieldtype": "Float", "precision": 0, "width": 110},
		{"label": _("Stop min"), "fieldname": "stop_minutes", "fieldtype": "Int", "width": 75},
	]
	data = shift_register(filters)
	summary = [
		{"label": _("Machine-shifts"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
	]
	return columns, data, None, None, summary
