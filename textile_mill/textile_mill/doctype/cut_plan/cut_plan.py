# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from textile_mill.manufacturing import available_batches, ceil_div, make_transfer_entry
from textile_mill.utils import batch_balance, get_settings, wh

GARMENT_SIZE_ATTRIBUTES = ("Garment Size", "T-Shirt Size")
# style stage -> (fabric store, cutting WIP, stitched FG store)
CUT_STORES = {
	"Garments": ("Fabric A Store", "Cutting WIP", "Unwashed Garment Store"),
	"Knit Garments": ("Finished Knit Store", "Knit Cutting WIP", "Knit FG Store"),
}


def variant_for(template: str, size: str) -> str | None:
	"""Variant of `template` whose size attribute equals `size`."""
	return frappe.db.get_value(
		"Item Variant Attribute",
		{"parent": ["like", f"{template}-%"], "attribute": ["in", GARMENT_SIZE_ATTRIBUTES], "attribute_value": size,
			"variant_of": template},
		"parent",
	)


def fabric_per_unit(item_code: str, fabric_item: str) -> float:
	bom = frappe.db.get_value("BOM", {"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1}, ["name", "quantity"], as_dict=True)
	if not bom:
		return 0.0
	qty = frappe.db.get_value("BOM Item", {"parent": bom.name, "item_code": fabric_item}, "stock_qty") or 0
	return flt(qty) / flt(bom.quantity or 1)


class CutPlan(Document):
	def validate(self) -> None:
		if not self.bundle_size:
			self.bundle_size = cint(get_settings().default_bundle_size) or 20
		if self.fabric_item:
			fabric = frappe.db.get_value("Item", self.fabric_item, ["stock_uom", "dm_target_gsm", "dm_width_inch"], as_dict=True)
			self.fabric_uom = "Kg" if fabric.stock_uom == "Kg" else "Meter"
			if self.fabric_uom == "Kg":
				self.fabric_gsm = self.fabric_gsm or fabric.dm_target_gsm
				self.fabric_width_inch = self.fabric_width_inch or fabric.dm_width_inch
				if not (flt(self.fabric_gsm) and flt(self.fabric_width_inch)):
					frappe.throw(_("Knit fabric needs GSM and width to convert the marker to kg."))
		for row in self.size_ratio:
			row.variant_item = row.variant_item or variant_for(self.style_template, row.size)
			if not row.variant_item:
				frappe.throw(_("No variant of {0} for size {1}.").format(self.style_template, row.size))
			row.pieces = cint(row.ratio) * cint(self.plies)
		self.pieces_per_marker = sum(cint(r.ratio) for r in self.size_ratio)
		self.total_pieces = sum(cint(r.pieces) for r in self.size_ratio)
		self.fabric_required_m = flt(
			self.marker_qty_per_ply() * cint(self.plies) * (1 + flt(self.end_bit_allowance_pct) / 100), 3
		)
		self.standard_fabric_m = flt(
			sum(cint(r.pieces) * fabric_per_unit(r.variant_item, self.fabric_item) for r in self.size_ratio), 3
		)
		if self.docstatus == 0:
			for roll in self.fabric_rolls:
				roll.available_m = batch_balance(roll.batch_no, roll.warehouse)
				if flt(roll.issued_m) > flt(roll.available_m) + 0.001:
					frappe.throw(_("Roll {0}: issued {1} exceeds available {2}.").format(roll.batch_no, roll.issued_m, roll.available_m))
		self.fabric_issued_m = flt(sum(flt(r.issued_m) for r in self.fabric_rolls), 3)
		self.cutting_variance_m = flt(self.fabric_issued_m - self.standard_fabric_m, 3)
		self.cutting_variance_pct = (
			flt(self.cutting_variance_m / self.standard_fabric_m * 100, 2) if self.standard_fabric_m else 0
		)

	def marker_qty_per_ply(self) -> float:
		"""Fabric per ply: metres, or kg from GSM × width × marker length for knit fabric."""
		if self.fabric_uom == "Kg":
			width_m = flt(self.fabric_width_inch) * 0.0254
			return flt(self.marker_length_m) * width_m * flt(self.fabric_gsm) / 1000
		return flt(self.marker_length_m)

	@frappe.whitelist()
	def allocate_rolls(self) -> None:
		"""FIFO: whole rolls until the requirement is met; the last roll is issued partially."""
		self.validate()
		warehouses = frappe.get_all(
			"Bin", filters={"item_code": self.fabric_item, "actual_qty": [">", 0]}, pluck="warehouse", distinct=True
		)
		preferred = wh(self.stores()[0], self.company)
		warehouses = sorted(set(warehouses), key=lambda w: (w != preferred, w))
		self.set("fabric_rolls", [])
		remaining = flt(self.fabric_required_m)
		for warehouse in warehouses:
			for batch, qty in available_batches(self.fabric_item, warehouse):
				if remaining <= 0.0001:
					break
				take = min(qty, remaining)
				self.append(
					"fabric_rolls",
					{"batch_no": batch, "warehouse": warehouse, "available_m": qty, "issued_m": flt(take, 3)},
				)
				remaining = flt(remaining - take, 3)
		if remaining > 0.001:
			frappe.msgprint(_("Short by {0}: not enough {1} in stock.").format(remaining, self.fabric_item))
		self.validate()
		if not self.is_new():
			self.save()

	def before_submit(self) -> None:
		if not self.fabric_rolls:
			frappe.throw(_("Allocate fabric rolls before submitting."))

	def on_submit(self) -> None:
		allocation = self.allocate_fabric_to_sizes()
		for row in self.size_ratio:
			wo = self.make_work_order(row)
			row.db_set("work_order", wo)
			self.transfer_materials(wo, row, allocation[row.name])
			self.make_bundles(wo, row)
		self.db_set("status", "Bundled")

	def allocate_fabric_to_sizes(self) -> dict[str, list[tuple[str, str, float]]]:
		"""Split issued rolls across sizes proportionally to pieces × fabric per piece (rolls in order)."""
		weights = {r.name: cint(r.pieces) * fabric_per_unit(r.variant_item, self.fabric_item) for r in self.size_ratio}
		total_w = sum(weights.values()) or 1
		targets = {k: flt(self.fabric_issued_m * w / total_w, 3) for k, w in weights.items()}
		last = self.size_ratio[-1].name
		targets[last] = flt(self.fabric_issued_m - sum(v for k, v in targets.items() if k != last), 3)

		rolls = [[r.batch_no, r.warehouse, flt(r.issued_m)] for r in self.fabric_rolls]
		out: dict[str, list] = {}
		for size_row in self.size_ratio:
			need = targets[size_row.name]
			out[size_row.name] = []
			for roll in rolls:
				if need <= 0.0001:
					break
				if roll[2] <= 0.0001:
					continue
				take = flt(min(roll[2], need), 3)
				out[size_row.name].append((roll[0], roll[1], take))
				roll[2] = flt(roll[2] - take, 3)
				need = flt(need - take, 3)
		return out

	def make_work_order(self, row) -> str:
		bom = frappe.db.get_value("BOM", {"item": row.variant_item, "is_default": 1, "is_active": 1, "docstatus": 1})
		wo = frappe.get_doc(
			{
				"doctype": "Work Order",
				"company": self.company,
				"production_item": row.variant_item,
				"bom_no": bom,
				"use_multi_level_bom": 0,
				"qty": row.pieces,
				"wip_warehouse": wh(self.stores()[1], self.company),
				"fg_warehouse": wh(self.stores()[2], self.company),
				"source_warehouse": wh(self.stores()[0], self.company),
				"scrap_warehouse": wh("Waste Store", self.company),
				"planned_start_date": f"{self.posting_date} 08:00:00",
				"cut_plan": self.name,
			}
		)
		wo.flags.ignore_permissions = True
		wo.insert()
		wo.submit()
		return wo.name

	def style_stage(self) -> str:
		return frappe.db.get_value("Item", self.style_template, "dm_stage") or "Garments"

	def stores(self) -> tuple[str, str, str]:
		return CUT_STORES.get(self.style_stage(), CUT_STORES["Garments"])

	def transfer_materials(self, work_order: str, row, fabric: list[tuple[str, str, float]]) -> None:
		"""Fabric = actual issued (batch-wise); trims = full standard quantity from their stores."""
		bom = frappe.db.get_value("Work Order", work_order, "bom_no")
		bom_qty = flt(frappe.db.get_value("BOM", bom, "quantity")) or 1
		rows = [{"item_code": self.fabric_item, "qty": q, "s_warehouse": w, "batch_no": b} for b, w, q in fabric]
		for item in frappe.get_all("BOM Item", filters={"parent": bom}, fields=["item_code", "stock_qty"]):
			if item.item_code == self.fabric_item:
				continue
			default_wh = frappe.db.get_value(
				"Item Default", {"parent": item.item_code, "company": self.company}, "default_warehouse"
			)
			rows.append(
				{"item_code": item.item_code, "qty": flt(item.stock_qty * cint(row.pieces) / bom_qty, 3), "s_warehouse": default_wh}
			)
		make_transfer_entry(
			work_order, rows, self.posting_date, "09:00:00", cut_plan=self.name, dm_stage=self.style_stage(),
			remarks=_("Cut Plan {0} - size {1}").format(self.name, row.size),
		)

	def make_bundles(self, work_order: str, row) -> None:
		size = cint(self.bundle_size) or 20
		pieces = cint(row.pieces)
		for n in range(1, ceil_div(pieces, size) + 1):
			qty = min(size, pieces - (n - 1) * size)
			frappe.get_doc(
				{
					"doctype": "Bundle Ticket",
					"cut_plan": self.name,
					"work_order": work_order,
					"variant_item": row.variant_item,
					"size": row.size,
					"bundle_no": n,
					"qty": qty,
					"status": "Cut",
				}
			).insert(ignore_permissions=True)

	def on_cancel(self) -> None:
		if frappe.flags.textile_demo_reset:
			return
		frappe.throw(_("Cut Plans cannot be cancelled after cutting; cancel the Work Orders individually."))

	@frappe.whitelist()
	def complete_stitched_work_orders(self) -> list[str]:
		from textile_mill.textile_mill.doctype.bundle_ticket.bundle_ticket import complete_work_order

		done = []
		for row in self.size_ratio:
			if row.work_order and complete_work_order(row.work_order, silent=True):
				done.append(row.work_order)
		return done
