from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from textile_mill.reports_lib import loom_efficiency

GROUP_FIELDS = {"Loom": "loom", "Weaver": "weaver", "Shift": "shift"}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = loom_efficiency(filters)
	group_field = GROUP_FIELDS.get(filters.get("group_by") or "")
	if group_field:
		columns, data = _grouped(rows, group_field)
	else:
		columns, data = _detail_columns(), rows

	by_loom = _aggregate(rows, "loom")
	chart = {
		"data": {"labels": list(by_loom), "datasets": [{"name": _("Efficiency %"), "values": [round(v["efficiency_pct"], 1) for v in by_loom.values()]}]},
		"type": "bar",
		"colors": ["#6a1b9a"],
	}
	return columns, data, None, chart


def _detail_columns():
	return [
		{"label": _("Loom Shift"), "fieldname": "loom_shift_production", "fieldtype": "Link", "options": "Loom Shift Production", "width": 130},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Shift"), "fieldname": "shift", "fieldtype": "Link", "options": "Mill Shift", "width": 70},
		{"label": _("Loom"), "fieldname": "loom", "fieldtype": "Link", "options": "Workstation", "width": 100},
		{"label": _("Weaver"), "fieldname": "weaver", "fieldtype": "Link", "options": "Employee", "width": 110},
		{"label": _("Loom Type"), "fieldname": "loom_type", "fieldtype": "Data", "width": 100},
		{"label": _("Meters"), "fieldname": "meters", "fieldtype": "Float", "width": 90},
		{"label": _("Kg"), "fieldname": "kg", "fieldtype": "Float", "width": 80},
		{"label": _("Efficiency %"), "fieldname": "efficiency_pct", "fieldtype": "Percent", "width": 100},
		{"label": _("Warp Breaks"), "fieldname": "warp_breaks", "fieldtype": "Int", "width": 95},
		{"label": _("Weft Breaks"), "fieldname": "weft_breaks", "fieldtype": "Int", "width": 95},
		{"label": _("Stop Minutes"), "fieldname": "stop_minutes", "fieldtype": "Int", "width": 95},
		{"label": _("Breaks / 100k Picks"), "fieldname": "breaks_per_100k_picks", "fieldtype": "Float", "precision": 2, "width": 130},
	]


def _aggregate(rows, field) -> dict:
	agg = defaultdict(lambda: {"meters": 0.0, "weighted": 0.0, "warp_breaks": 0, "weft_breaks": 0, "stop_minutes": 0, "rows": 0})
	for r in rows:
		a = agg[r[field]]
		output = flt(r.meters) or flt(r.kg)
		a["meters"] += output
		a["weighted"] += output * flt(r.efficiency_pct)
		a["warp_breaks"] += r.warp_breaks or 0
		a["weft_breaks"] += r.weft_breaks or 0
		a["stop_minutes"] += r.stop_minutes or 0
		a["rows"] += 1
	for a in agg.values():
		a["efficiency_pct"] = a["weighted"] / a["meters"] if a["meters"] else 0
	return dict(sorted(agg.items()))


def _grouped(rows, field):
	label = next(k for k, v in GROUP_FIELDS.items() if v == field)
	columns = [
		{"label": _(label), "fieldname": field, "fieldtype": "Data", "width": 130},
		{"label": _("Loom Shifts"), "fieldname": "rows", "fieldtype": "Int", "width": 100},
		{"label": _("Output (m or kg)"), "fieldname": "meters", "fieldtype": "Float", "width": 110},
		{"label": _("Efficiency % (weighted)"), "fieldname": "efficiency_pct", "fieldtype": "Percent", "width": 150},
		{"label": _("Warp Breaks"), "fieldname": "warp_breaks", "fieldtype": "Int", "width": 100},
		{"label": _("Weft Breaks"), "fieldname": "weft_breaks", "fieldtype": "Int", "width": 100},
		{"label": _("Stop Minutes"), "fieldname": "stop_minutes", "fieldtype": "Int", "width": 100},
	]
	return columns, [{field: key, **vals} for key, vals in _aggregate(rows, field).items()]
