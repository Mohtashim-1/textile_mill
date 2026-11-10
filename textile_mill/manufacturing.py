"""Shared stock/manufacturing helpers used by shop-floor DocTypes and the demo journey."""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, get_time, getdate


# ---------------------------------------------------------------- batches
def new_batch(item_code: str, batch_id: str | None = None, **fields) -> str:
	"""Create a Batch (id from the item's batch series unless given) with textile custom fields."""
	if batch_id and frappe.db.exists("Batch", batch_id):
		if fields:
			frappe.db.set_value("Batch", batch_id, fields)
		return batch_id
	doc = frappe.get_doc({"doctype": "Batch", "item": item_code, "batch_id": batch_id, **fields})
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def available_batches(item_code: str, warehouse: str) -> list[tuple[str, float]]:
	"""FIFO (by batch creation) list of (batch_no, qty) with positive balance in a warehouse."""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	rows = get_batch_qty(item_code=item_code, warehouse=warehouse) or []
	qty = {r["batch_no"]: flt(r["qty"]) for r in rows if flt(r["qty"]) > 0.0001}
	if not qty:
		return []
	created = dict(
		frappe.get_all("Batch", filters={"name": ["in", list(qty)]}, fields=["name", "creation"], as_list=True)
	)
	return [(b, qty[b]) for b in sorted(qty, key=lambda b: (created.get(b), b))]


def pick_batches(item_code: str, warehouse: str, qty: float, exclude: dict | None = None) -> list[tuple[str, float]]:
	"""Allocate `qty` FIFO across batches; `exclude` maps batch -> qty already allocated elsewhere."""
	exclude = exclude or {}
	out, remaining = [], flt(qty, 6)
	for batch, bal in available_batches(item_code, warehouse):
		bal = flt(bal - exclude.get(batch, 0), 6)
		if bal <= 0:
			continue
		take = min(bal, remaining)
		out.append((batch, take))
		remaining = flt(remaining - take, 6)
		if remaining <= 0.0001:
			break
	if remaining > 0.001:
		frappe.throw(
			_("Not enough batch stock of {0} in {1}: short by {2}").format(item_code, warehouse, remaining)
		)
	return out


def split_rows_by_batch(se) -> None:
	"""Give every outward batch-tracked row an explicit batch (FIFO), splitting rows as needed.

	Keeps genealogy deterministic (Part B §11.4) instead of relying on auto bundle picking.
	"""
	skip = {"name", "idx", "parent", "parentfield", "parenttype", "doctype", "creation", "modified"}
	out, used = [], {}
	for row in se.items:
		r = {k: v for k, v in row.as_dict().items() if k not in skip}
		has_batch = frappe.get_cached_value("Item", row.item_code, "has_batch_no")
		if not (row.s_warehouse and has_batch and not row.batch_no and not row.serial_and_batch_bundle):
			out.append(r)
			continue
		key = (row.item_code, row.s_warehouse)
		cf = flt(row.conversion_factor) or 1
		for batch, q in pick_batches(row.item_code, row.s_warehouse, flt(row.transfer_qty or row.qty), used.get(key)):
			out.append({**r, "batch_no": batch, "qty": flt(q / cf, 6), "transfer_qty": q, "use_serial_batch_fields": 1})
			used.setdefault(key, {})
			used[key][batch] = used[key].get(batch, 0) + q
	se.set("items", [])
	for r in out:
		se.append("items", r)


# ---------------------------------------------------------------- job cards
def complete_operations(
	work_order: str, qty: float, end: datetime | str, employee: str | None = None, remarks: str | None = None
) -> None:
	"""Complete job cards so `qty` more units can be manufactured (v15 blocks Manufacture otherwise).

	Draft job cards created at Work Order submit are split so each production document
	gets its own submitted job card for exactly its quantity.
	"""
	from erpnext.manufacturing.doctype.work_order.work_order import create_job_card

	wo = frappe.get_doc("Work Order", work_order)
	if not wo.operations:
		return
	minutes = [flt(op.time_in_mins) * flt(qty) / flt(wo.qty) for op in wo.operations]
	cursor = get_datetime(end) - timedelta(minutes=sum(minutes))

	for op, mins in zip(wo.operations, minutes):
		needed = flt(wo.produced_qty) + flt(qty) - flt(op.completed_qty)
		if needed <= 0.0001:
			cursor += timedelta(minutes=mins)
			continue
		draft = frappe.get_all(
			"Job Card",
			filters={"operation_id": op.name, "docstatus": 0, "is_corrective_job_card": 0},
			fields=["name", "for_quantity"],
			order_by="creation asc",
			limit=1,
		)
		if draft and flt(draft[0].for_quantity) > needed + 0.0001:
			frappe.db.set_value("Job Card", draft[0].name, "for_quantity", flt(draft[0].for_quantity) - needed)
			jc = None
		elif draft:
			jc = frappe.get_doc("Job Card", draft[0].name)
			needed = flt(jc.for_quantity)
		else:
			jc = None
		if jc is None:
			op.job_card_qty = needed
			jc = create_job_card(wo, op)
		jc.for_quantity = needed
		jc.posting_date = getdate(cursor + timedelta(minutes=mins))
		jc.set("time_logs", [])
		jc.append(
			"time_logs",
			{
				"from_time": cursor,
				"to_time": cursor + timedelta(minutes=max(mins, 1)),
				"time_in_mins": max(mins, 1),
				"completed_qty": needed,
				"employee": employee,
			},
		)
		if remarks:
			jc.remarks = remarks
		jc.flags.ignore_permissions = True
		jc.flags.ignore_mandatory = True
		jc.save()
		jc.submit()
		cursor += timedelta(minutes=mins)


def make_corrective_job_card(
	work_order: str,
	for_operation: str,
	corrective_operation: str,
	minutes: float,
	start: datetime | str,
	remarks: str,
	employee: str | None = None,
) -> str:
	"""Corrective (re-process) job card against a completed operation (Part B §11.5)."""
	from erpnext.manufacturing.doctype.job_card.job_card import make_corrective_job_card as erp_make

	source = frappe.get_all(
		"Job Card",
		filters={"work_order": work_order, "operation": for_operation, "docstatus": 1, "is_corrective_job_card": 0},
		pluck="name",
		order_by="creation desc",
		limit=1,
	)
	if not source:
		frappe.throw(_("Complete a {0} job card before making a corrective one.").format(for_operation))
	jc = erp_make(source[0], operation=corrective_operation, for_operation=for_operation)
	jc.workstation = frappe.db.get_value("Operation", corrective_operation, "workstation") or jc.workstation
	jc.hour_rate = frappe.db.get_value("Workstation", jc.workstation, "hour_rate")
	start = get_datetime(start)
	jc.posting_date = getdate(start)
	jc.remarks = remarks
	jc.set("time_logs", [])
	jc.append(
		"time_logs",
		{
			"from_time": start,
			"to_time": start + timedelta(minutes=minutes),
			"time_in_mins": minutes,
			"completed_qty": jc.for_quantity,
			"employee": employee,
		},
	)
	jc.flags.ignore_permissions = True
	jc.insert()
	jc.submit()
	return jc.name


# ---------------------------------------------------------------- stock entries
def _posting(se, posting_date=None, posting_time=None) -> None:
	if posting_date:
		se.set_posting_time = 1
		se.posting_date = getdate(posting_date)
		se.posting_time = str(get_time(posting_time or "12:00:00"))


def make_transfer_entry(
	work_order: str,
	rows: list[dict],
	posting_date=None,
	posting_time=None,
	submit: bool = True,
	remarks: str | None = None,
	fg_qty: float | None = None,
	**links,
):
	"""Material Transfer for Manufacture with explicit rows: {item_code, qty, s_warehouse, batch_no?}.

	Pass fg_qty=0 for top-up transfers so the Work Order's transferred quantity is not counted twice.
	"""
	wo = frappe.get_doc("Work Order", work_order)
	se = frappe.new_doc("Stock Entry")
	se.update(
		{
			"stock_entry_type": "Material Transfer for Manufacture",
			"purpose": "Material Transfer for Manufacture",
			"company": wo.company,
			"work_order": wo.name,
			"bom_no": wo.bom_no,
			"from_bom": 1,
			"fg_completed_qty": wo.qty if fg_qty is None else fg_qty,
			"to_warehouse": wo.wip_warehouse,
			"remarks": remarks,
			**links,
		}
	)
	_posting(se, posting_date, posting_time)
	for r in rows:
		uom = frappe.get_cached_value("Item", r["item_code"], "stock_uom")
		se.append(
			"items",
			{
				"item_code": r["item_code"],
				"qty": flt(r["qty"], 6),
				"uom": uom,
				"stock_uom": uom,
				"conversion_factor": 1,
				"transfer_qty": flt(r["qty"], 6),
				"s_warehouse": r["s_warehouse"],
				"t_warehouse": wo.wip_warehouse,
				"batch_no": r.get("batch_no"),
				"use_serial_batch_fields": 1 if r.get("batch_no") else 0,
			},
		)
	split_rows_by_batch(se)
	se.flags.ignore_permissions = True
	se.insert()
	if submit:
		se.submit()
	return se


def make_material_entry(
	purpose: str,
	company: str,
	rows: list[dict],
	posting_date=None,
	posting_time=None,
	submit: bool = True,
	remarks: str | None = None,
	**header,
):
	"""Generic Material Issue / Receipt / Transfer / Consumption entry with FIFO batch picking."""
	se = frappe.new_doc("Stock Entry")
	se.update({"stock_entry_type": purpose, "purpose": purpose, "company": company, "remarks": remarks, **header})
	_posting(se, posting_date, posting_time)
	for r in rows:
		uom = frappe.get_cached_value("Item", r["item_code"], "stock_uom")
		se.append(
			"items",
			{
				"uom": uom,
				"stock_uom": uom,
				"conversion_factor": 1,
				"transfer_qty": flt(r["qty"], 6),
				"use_serial_batch_fields": 1 if r.get("batch_no") else 0,
				**r,
			},
		)
	split_rows_by_batch(se)
	se.flags.ignore_permissions = True
	se.insert()
	if submit:
		se.submit()
	return se


def build_manufacture_entry(
	work_order: str,
	qty: float,
	posting_date=None,
	posting_time=None,
	fg_batch: str | None = None,
	remarks: str | None = None,
	**links,
):
	"""Draft Manufacture entry (backflush per Manufacturing Settings), FG batch set explicitly."""
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	se = frappe.get_doc(make_stock_entry(work_order, "Manufacture", qty))
	_posting(se, posting_date, posting_time)
	se.remarks = remarks
	se.update(links)
	for row in se.items:
		if row.is_finished_item and fg_batch:
			row.batch_no = fg_batch
			row.use_serial_batch_fields = 1
	split_rows_by_batch(se)
	se.flags.ignore_permissions = True
	return se


def make_manufacture_entry(
	work_order: str,
	qty: float,
	posting_date=None,
	posting_time=None,
	fg_batch: str | None = None,
	employee: str | None = None,
	submit: bool = True,
	remarks: str | None = None,
	**links,
):
	"""Complete job cards for `qty`, then create (and optionally submit) the Manufacture entry."""
	end = get_datetime(f"{getdate(posting_date or frappe.utils.today())} {get_time(posting_time or '12:00:00')}")
	complete_operations(work_order, qty, end, employee)
	se = build_manufacture_entry(work_order, qty, posting_date, posting_time, fg_batch, remarks, **links)
	se.insert()
	if submit:
		se.submit()
	return se


def cancel_linked(doctype: str, name: str | None) -> None:
	if name and frappe.db.get_value(doctype, name, "docstatus") == 1:
		doc = frappe.get_doc(doctype, name)
		doc.flags.ignore_permissions = True
		doc.cancel()


def shift_hours() -> int:
	return 8


def ceil_div(a: int, b: int) -> int:
	return -(-cint(a) // cint(b)) if cint(b) else 0
