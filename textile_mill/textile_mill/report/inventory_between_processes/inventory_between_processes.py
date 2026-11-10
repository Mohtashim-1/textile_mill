from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from textile_mill.reports_lib import inventory_between_processes


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = inventory_between_processes(filters)
	if filters.get("group_by_warehouse_group"):
		columns, data = _summary(rows)
	else:
		columns = [
			{"label": _("Warehouse Group"), "fieldname": "warehouse_group", "fieldtype": "Link", "options": "Warehouse", "width": 190},
			{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 190},
			{"label": _("Status"), "fieldname": "dm_inventory_status", "fieldtype": "Data", "width": 85},
			{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
			{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 110},
			{"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 70},
			{"label": _("Value"), "fieldname": "value", "fieldtype": "Currency", "width": 140},
		]
		data = rows

	by_group = defaultdict(float)
	for r in rows:
		by_group[r.warehouse_group] += flt(r.value)
	chart = {
		"data": {"labels": list(by_group), "datasets": [{"name": _("Value"), "values": [round(v) for v in by_group.values()]}]},
		"type": "bar",
		"colors": ["#00838f"],
	}
	return columns, data, None, chart


def _summary(rows):
	groups: dict[tuple, dict] = {}
	for r in rows:
		key = (r.warehouse_group, r.stock_uom)
		g = groups.setdefault(key, {"warehouse_group": r.warehouse_group, "dm_inventory_status": r.dm_inventory_status,
			"stock_uom": r.stock_uom, "qty": 0.0, "value": 0.0, "items": set()})
		g["qty"] += flt(r.qty)
		g["value"] += flt(r.value)
		g["items"].add(r.item_code)
	data = [dict(g, items=len(g["items"])) for g in groups.values()]
	columns = [
		{"label": _("Warehouse Group"), "fieldname": "warehouse_group", "fieldtype": "Link", "options": "Warehouse", "width": 200},
		{"label": _("Status"), "fieldname": "dm_inventory_status", "fieldtype": "Data", "width": 90},
		{"label": _("Items"), "fieldname": "items", "fieldtype": "Int", "width": 70},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 120},
		{"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 70},
		{"label": _("Value"), "fieldname": "value", "fieldtype": "Currency", "width": 150},
	]
	return columns, data
