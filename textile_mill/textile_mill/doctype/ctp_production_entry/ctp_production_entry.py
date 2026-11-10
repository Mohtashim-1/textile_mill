# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime

from textile_mill.constants import CONSUMABLE_ITEM_GROUPS
from textile_mill.manufacturing import (
	build_manufacture_entry,
	cancel_linked,
	complete_operations,
	make_transfer_entry,
	new_batch,
)
from textile_mill.utils import wh

SECONDS_ITEM = {"PT-500-WHT": "TWL-SECONDS"}
RAGS_ITEM = "WST-RAGS"
WASTE_ITEM = "WST-CTP"
SCRAP_STORE = "Waste Store"
SECONDS_STORE = "Seconds Store"


def bom_rows(bom: str) -> tuple[float, list[dict]]:
	qty = flt(frappe.db.get_value("BOM", bom, "quantity")) or 1
	rows = frappe.get_all(
		"BOM Item", filters={"parent": bom}, fields=["item_code", "stock_qty", "item_name"], order_by="idx"
	)
	return qty, rows


def main_material(bom: str) -> tuple[str | None, float]:
	"""(source item, qty per piece) — the first BOM row that is not a consumable (trims, chemicals, packing)."""
	qty, rows = bom_rows(bom)
	for r in rows:
		group = frappe.get_cached_value("Item", r.item_code, "item_group")
		if group not in CONSUMABLE_ITEM_GROUPS:
			return r.item_code, flt(r.stock_qty) / qty
	return None, 0.0


def default_warehouse(item_code: str, company: str) -> str | None:
	return frappe.db.get_value("Item Default", {"parent": item_code, "company": company}, "default_warehouse")


class CTPProductionEntry(Document):
	def validate(self) -> None:
		wo = frappe.db.get_value(
			"Work Order", self.work_order, ["docstatus", "dm_stage", "production_item", "bom_no", "company"], as_dict=True
		)
		if not wo or wo.docstatus != 1:
			frappe.throw(_("Work Order {0} must be submitted.").format(self.work_order))
		if wo.dm_stage != "Cut-to-Piece":
			frappe.throw(_("Work Order {0} is not a Cut-to-Piece order.").format(self.work_order))
		self.company = self.company or wo.company
		self.product_item = wo.production_item
		self.source_item, per_piece = main_material(wo.bom_no)

		for row in self.source_batches:
			batch_item = frappe.db.get_value("Batch", row.batch_no, "item")
			if batch_item != self.source_item:
				frappe.throw(_("Row {0}: batch {1} is {2}, expected {3}.").format(row.idx, row.batch_no, batch_item, self.source_item))
			if flt(row.qty_issued) <= 0:
				frappe.throw(_("Row {0}: quantity issued must be greater than zero.").format(row.idx))

		issued = sum(flt(r.qty_issued) for r in self.source_batches)
		self.pieces_planned = math.floor(issued / per_piece + 1e-6) if per_piece and issued else self.pieces_planned
		if not self.pieces_planned:
			self.pieces_planned = self.pieces_cut

		if self.pieces_cut <= 0:
			frappe.throw(_("Pieces cut must be greater than zero."))
		if (self.pieces_a or 0) + (self.pieces_seconds or 0) > self.pieces_cut:
			frappe.throw(_("A-grade + seconds ({0}) cannot exceed pieces cut ({1}).").format(
				(self.pieces_a or 0) + (self.pieces_seconds or 0), self.pieces_cut))
		if self.pieces_a <= 0:
			frappe.throw(_("A-grade pieces must be greater than zero."))
		for field in ("seconds_weight_kg", "rags_kg", "cutting_waste_kg"):
			if flt(self.get(field)) < 0:
				frappe.throw(_("{0} cannot be negative.").format(self.meta.get_label(field)))

		self.ctp_yield_pct = flt(self.pieces_a / self.pieces_planned * 100, 2) if self.pieces_planned else 0
		self.seconds_pct = flt((self.pieces_seconds or 0) / self.pieces_cut * 100, 2)

	def before_submit(self) -> None:
		needs_check = flt(frappe.get_cached_value("Item", self.product_item, "dm_target_weight_kg")) > 0
		if needs_check and not self.weight_check:
			frappe.throw(_("Link a submitted Piece Weight Check for {0} before submitting.").format(self.product_item))
		if self.weight_check:
			check = frappe.db.get_value("Piece Weight Check", self.weight_check, ["docstatus", "item_code"], as_dict=True)
			if not check or check.docstatus != 1 or check.item_code != self.product_item:
				frappe.throw(_("Piece Weight Check {0} must be submitted and for {1}.").format(self.weight_check, self.product_item))

	def on_submit(self) -> None:
		transfer = self.make_transfer() if self.source_batches else None
		se = self.make_manufacture()
		self.db_set({"transfer_entry": transfer, "stock_entry": se})

	def on_cancel(self) -> None:
		cancel_linked("Stock Entry", self.stock_entry)
		cancel_linked("Stock Entry", self.transfer_entry)

	# ------------------------------------------------------------ stock
	def consumption_rows(self) -> list[dict]:
		"""Issued fabric batches + trims for every piece cut (seconds use trims too)."""
		bom = frappe.db.get_value("Work Order", self.work_order, "bom_no")
		qty, rows = bom_rows(bom)
		out = [
			{"item_code": self.source_item, "qty": flt(r.qty_issued), "s_warehouse": r.warehouse, "batch_no": r.batch_no}
			for r in self.source_batches
		]
		for r in rows:
			if r.item_code == self.source_item:
				continue
			out.append(
				{
					"item_code": r.item_code,
					"qty": flt(flt(r.stock_qty) / qty * self.pieces_cut, 4),
					"s_warehouse": default_warehouse(r.item_code, self.company),
				}
			)
		return out

	def make_transfer(self) -> str:
		wo = frappe.get_doc("Work Order", self.work_order)
		remaining = max(flt(wo.qty) - flt(wo.material_transferred_for_manufacturing), 0)
		se = make_transfer_entry(
			self.work_order,
			self.consumption_rows(),
			self.posting_date,
			self.posting_time,
			remarks=_("CTP Production Entry {0} — fabric and trims issue").format(self.name),
			fg_qty=min(self.pieces_cut, remaining),
			ctp_production_entry=self.name,
		)
		return se.name

	def make_manufacture(self) -> str:
		wo = frappe.get_doc("Work Order", self.work_order)
		complete_operations(self.work_order, self.pieces_a, get_datetime(f"{self.posting_date} {self.posting_time}"))
		batch = new_batch(
			self.product_item,
			manufacturing_date=self.posting_date,
			dm_stage="Cut-to-Piece",
			dm_grade="A",
			dm_source_doctype=self.doctype,
			dm_source_doc=self.name,
		)
		se = build_manufacture_entry(
			self.work_order,
			self.pieces_a,
			self.posting_date,
			self.posting_time,
			fg_batch=batch,
			remarks=_("CTP Production Entry {0}").format(self.name),
			ctp_production_entry=self.name,
		)
		if self.source_batches:
			self.replace_consumption(se, wo.wip_warehouse)
		self.set_scrap_rows(se)
		se.insert()
		se.submit()
		return se.name

	def replace_consumption(self, se, wip: str) -> None:
		"""Consume exactly what this entry issued: all cut fabric goes into A pieces, seconds or scrap."""
		keep = [r for r in se.items if r.is_finished_item]
		se.set("items", [])
		for r in self.consumption_rows():
			uom = frappe.get_cached_value("Item", r["item_code"], "stock_uom")
			se.append(
				"items",
				{
					"item_code": r["item_code"],
					"qty": r["qty"],
					"transfer_qty": r["qty"],
					"uom": uom,
					"stock_uom": uom,
					"conversion_factor": 1,
					"s_warehouse": wip,
					"batch_no": r.get("batch_no"),
					"use_serial_batch_fields": 1 if r.get("batch_no") else 0,
				},
			)
		for row in keep:
			se.append("items", row.as_dict(no_default_fields=True))

	def set_scrap_rows(self, se) -> None:
		for row in [r for r in se.items if r.is_scrap_item]:
			se.remove(row)
		seconds_item = SECONDS_ITEM.get(self.source_item)
		waste_kg = flt(self.cutting_waste_kg) + (0 if seconds_item else flt(self.seconds_weight_kg))
		scraps = [
			(seconds_item, flt(self.seconds_weight_kg) if seconds_item else 0, SECONDS_STORE),
			(RAGS_ITEM, flt(self.rags_kg), SCRAP_STORE),
			(WASTE_ITEM, waste_kg, SCRAP_STORE),
		]
		for item, qty, store in scraps:
			if not item or qty <= 0:
				continue
			uom = frappe.get_cached_value("Item", item, "stock_uom")
			se.append(
				"items",
				{
					"item_code": item,
					"qty": qty,
					"transfer_qty": qty,
					"uom": uom,
					"stock_uom": uom,
					"conversion_factor": 1,
					"t_warehouse": wh(store, self.company),
					"is_scrap_item": 1,
					"set_basic_rate_manually": 1,
					"basic_rate": flt(frappe.get_cached_value("Item", item, "valuation_rate")),
				},
			)
