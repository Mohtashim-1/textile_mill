"""Home Textile report queries (Part D §D8), shared by script reports and dashboard KPIs."""

import math

import frappe
from frappe.utils import flt

from textile_mill.reports_lib import _period
from textile_mill.utils import item_rate


def _conditions(filters, alias: str, date_field: str, company: bool = True) -> tuple[list[str], dict]:
	f, company_name, from_date, to_date = _period(filters)
	conditions = [f"{alias}.docstatus = 1", f"{alias}.{date_field} between %(from)s and %(to)s"]
	values = {"from": from_date, "to": to_date}
	if company and company_name:
		conditions.append(f"{alias}.company = %(company)s")
		values["company"] = company_name
	return conditions, {**values, "_f": f}


# ---------------------------------------------------------------- D8.1 CTP yield & grading
def ctp_entries(filters) -> list[dict]:
	conditions, values = _conditions(filters, "c", "posting_date")
	f = values.pop("_f")
	for key in ("product_item", "line"):
		if f.get(key):
			conditions.append(f"c.{key} = %({key})s")
			values[key] = f.get(key)
	return frappe.db.sql(
		f"""select c.name as ctp_production_entry, c.posting_date, c.work_order, c.product_item, c.source_item, c.line,
			c.pieces_planned, c.pieces_cut, c.pieces_a, c.pieces_seconds, c.seconds_weight_kg, c.rags_kg, c.cutting_waste_kg,
			c.ctp_yield_pct, c.seconds_pct, c.weight_check, c.stock_entry,
			(select sum(qty_issued) from `tabCTP Source Batch` b where b.parent = c.name) as fabric_issued
		from `tabCTP Production Entry` c where {" and ".join(conditions)}
		order by c.posting_date, c.name""",  # noqa: S608
		values,
		as_dict=True,
	)


def ctp_totals(filters) -> dict:
	rows = ctp_entries(filters)
	planned = sum(r.pieces_planned or 0 for r in rows)
	cut = sum(r.pieces_cut or 0 for r in rows)
	return {
		"planned": planned,
		"cut": cut,
		"a": sum(r.pieces_a or 0 for r in rows),
		"seconds": sum(r.pieces_seconds or 0 for r in rows),
		"rows": rows,
	}


# ---------------------------------------------------------------- D8.2 weight compliance
def weight_checks(filters) -> list[dict]:
	"""Per check: variance vs target, CV, implied GSM and cotton give-away on the pieces it released."""
	conditions, values = _conditions(filters, "w", "posting_date", company=False)
	f = values.pop("_f")
	if f.get("item_code"):
		conditions.append("w.item_code = %(item_code)s")
		values["item_code"] = f.get("item_code")
	rows = frappe.db.sql(
		f"""select w.name as piece_weight_check, w.posting_date, w.item_code, w.work_order, w.target_weight_kg,
			w.tolerance_pct, w.sample_count, w.avg_weight_kg, w.min_weight_kg, w.max_weight_kg, w.cv_pct, w.variance_pct,
			w.implied_gsm, w.result,
			(select sum(c.pieces_a + c.pieces_seconds) from `tabCTP Production Entry` c
				where c.weight_check = w.name and c.docstatus = 1) as pieces
		from `tabPiece Weight Check` w where {" and ".join(conditions)}
		order by w.posting_date, w.name""",  # noqa: S608
		values,
		as_dict=True,
	)
	for r in rows:
		r.pieces = flt(r.pieces)
		r.giveaway_kg = flt((flt(r.avg_weight_kg) - flt(r.target_weight_kg)) * r.pieces, 2)
		source = frappe.db.get_value("BOM Item", {"parent": frappe.db.get_value(
			"BOM", {"item": r.item_code, "is_default": 1, "docstatus": 1}), "idx": 1}, "item_code")
		r.fabric_rate = item_rate(source) if source else 0
		r.giveaway_value = flt(r.giveaway_kg * flt(r.fabric_rate), 2)
	return rows


def weight_variance_pct(filters) -> float | None:
	"""Piece-weighted average variance % (signed: + = overweight / cotton give-away)."""
	rows = weight_checks(filters)
	weights = [r.pieces or r.sample_count or 1 for r in rows]
	total = sum(weights)
	return sum(flt(r.variance_pct) * w for r, w in zip(rows, weights)) / total if total else None


# ---------------------------------------------------------------- D8.3 set completion
def set_items() -> list[str]:
	return frappe.get_all(
		"Item", filters={"dm_stage": "Set Assembly", "disabled": 0, "has_variants": 0}, pluck="name", order_by="name"
	)


def usable_qty(item_code: str, company: str | None = None) -> float:
	return flt(frappe.db.sql(
		"""select sum(b.actual_qty) from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
		where b.item_code = %s and ifnull(w.dm_inventory_status, 'Usable') = 'Usable'
		and (%s is null or w.company = %s)""",
		(item_code, company, company),
	)[0][0])


def open_so_qty(item_code: str, company: str | None = None) -> float:
	return flt(frappe.db.sql(
		"""select sum(soi.stock_qty - soi.delivered_qty * soi.conversion_factor) from `tabSales Order Item` soi
		join `tabSales Order` so on so.name = soi.parent where so.docstatus = 1 and soi.item_code = %s
		and so.status not in ('Closed', 'Completed') and (%s is null or so.company = %s)""",
		(item_code, company, company),
	)[0][0])


def set_completion(filters=None) -> list[dict]:
	"""Buildable sets = min(component available ÷ qty per set); shortfall vs open Sales Orders."""
	f = frappe._dict(filters or {})
	company = f.get("company")
	out = []
	for item in [f.item_code] if f.get("item_code") else set_items():
		bom = frappe.db.get_value("BOM", {"item": item, "is_default": 1, "is_active": 1, "docstatus": 1})
		if not bom:
			continue
		bom_qty = flt(frappe.db.get_value("BOM", bom, "quantity")) or 1
		components = []
		for c in frappe.get_all("BOM Item", filters={"parent": bom}, fields=["item_code", "stock_qty"], order_by="idx"):
			per_set = flt(c.stock_qty) / bom_qty
			available = usable_qty(c.item_code, company)
			components.append((c.item_code, per_set, available, math.floor(available / per_set + 1e-9) if per_set else 0))
		limiting = min(components, key=lambda c: c[3]) if components else None
		buildable = limiting[3] if limiting else 0
		on_hand = usable_qty(item, company)
		open_qty = open_so_qty(item, company)
		need = max(open_qty - on_hand, 0)
		shortfall = max(need - buildable, 0)
		out.append(frappe._dict(
			item_code=item,
			bom=bom,
			on_hand=on_hand,
			buildable=buildable,
			limiting_component=limiting[0] if limiting and need else None,
			limiting_available=limiting[2] if limiting else 0,
			open_so_qty=open_qty,
			shortfall=shortfall,
			completion_pct=flt(min((on_hand + buildable) / open_qty, 1) * 100, 1) if open_qty else 100.0,
			components=", ".join(f"{c[0]} {flt(c[2], 0):g}/{c[1]:g}" for c in components),
		))
	return out


def set_completion_pct(filters=None) -> float | None:
	rows = [r for r in set_completion(filters) if r.open_so_qty]
	total = sum(r.open_so_qty for r in rows)
	return sum(min(r.on_hand + r.buildable, r.open_so_qty) for r in rows) / total * 100 if total else None


# ---------------------------------------------------------------- D8.4 carton & shipment summary
def shipments(filters) -> list[dict]:
	conditions, values = _conditions(filters, "c", "posting_date")
	f = values.pop("_f")
	if f.get("customer"):
		conditions.append("c.customer = %(customer)s")
		values["customer"] = f.get("customer")
	return frappe.db.sql(
		f"""select c.sales_order, so.po_no, c.customer, c.item_code, count(c.name) as packing_lists,
			sum(c.total_cartons) as cartons, sum(c.total_qty) as qty, sum(c.total_net_kg) as net_kg,
			sum(c.total_gross_kg) as gross_kg, sum(c.total_cbm) as cbm,
			group_concat(distinct c.delivery_note) as delivery_notes,
			sum(if(dn.docstatus = 1, c.total_cartons, 0)) as cartons_shipped,
			max(dn.posting_date) as shipped_on
		from `tabCarton Packing List` c join `tabSales Order` so on so.name = c.sales_order
		left join `tabDelivery Note` dn on dn.name = c.delivery_note
		where {" and ".join(conditions)}
		group by c.sales_order, c.item_code order by c.sales_order""",  # noqa: S608
		values,
		as_dict=True,
	)


def cartons_shipped(filters) -> float:
	_f, company, from_date, to_date = _period(filters)
	return flt(frappe.db.sql(
		"""select sum(c.total_cartons) from `tabCarton Packing List` c join `tabDelivery Note` dn on dn.name = c.delivery_note
		where c.docstatus = 1 and dn.docstatus = 1 and dn.posting_date between %s and %s and (%s is null or c.company = %s)""",
		(from_date, to_date, company, company),
	)[0][0])
