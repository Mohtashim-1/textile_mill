# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from textile_mill.manufacturing import cancel_linked, make_manufacture_entry, new_batch, shift_hours

INCH_PER_M = 39.37


def theoretical_meters(rpm: float, efficiency_pct: float, picks_per_inch: float, hours: float = 8) -> float:
	"""rpm × 60 × hours × efficiency ÷ (ppi × 39.37) — picks woven converted to metres."""
	if not (rpm and picks_per_inch):
		return 0.0
	return flt(flt(rpm) * 60 * hours * flt(efficiency_pct) / 100 / (flt(picks_per_inch) * INCH_PER_M), 2)


class LoomShiftProduction(Document):
	def validate(self) -> None:
		self.validate_work_order()
		is_terry = self.loom_type == "Terry"
		self.output_uom = "Kg" if is_terry else "Meter"
		for row in self.looms:
			if is_terry:
				if flt(row.kg) <= 0:
					frappe.throw(_("Row {0}: enter Kg for terry looms.").format(row.idx))
			elif not flt(row.meters):
				row.meters = theoretical_meters(row.rpm, row.efficiency_pct, row.picks_per_inch or 44, shift_hours())
		self.total_meters = flt(sum(flt(r.meters) for r in self.looms), 2)
		self.total_kg = flt(sum(flt(r.kg) for r in self.looms), 3)
		self.total_stop_minutes = sum(int(r.stop_minutes or 0) for r in self.looms)
		weight_field = "kg" if is_terry else "meters"
		total = sum(flt(r.get(weight_field)) for r in self.looms)
		self.avg_efficiency_pct = (
			flt(sum(flt(r.efficiency_pct) * flt(r.get(weight_field)) for r in self.looms) / total, 2) if total else 0
		)
		if self.output_qty <= 0:
			frappe.throw(_("Total output must be greater than zero."))

	@property
	def output_qty(self) -> float:
		return self.total_kg if self.loom_type == "Terry" else self.total_meters

	def validate_work_order(self) -> None:
		wo = frappe.db.get_value("Work Order", self.work_order, ["docstatus", "dm_stage", "production_item"], as_dict=True)
		if not wo or wo.docstatus != 1:
			frappe.throw(_("Work Order {0} must be submitted.").format(self.work_order))
		if wo.dm_stage not in ("Weaving", "Terry Weaving", "Flat Weaving"):
			frappe.throw(_("Work Order {0} is not a weaving order.").format(self.work_order))

	def on_submit(self) -> None:
		item, stage, bom = frappe.db.get_value("Work Order", self.work_order, ["production_item", "dm_stage", "bom_no"])
		# Grey terry needs a QI on the FG row: the entry stays draft until the inspection is recorded.
		needs_qi = frappe.db.get_value("BOM", bom, "inspection_required")
		batch = new_batch(
			item,
			manufacturing_date=self.posting_date,
			dm_stage=stage,
			dm_loom_list=", ".join(r.loom for r in self.looms),
			dm_source_doctype=self.doctype,
			dm_source_doc=self.name,
		)
		se = make_manufacture_entry(
			self.work_order,
			self.output_qty,
			self.posting_date,
			self.posting_time,
			fg_batch=batch,
			employee=self.supervisor,
			submit=not needs_qi,
			remarks=_("Loom Shift Production {0}").format(self.name),
			loom_shift_production=self.name,
			dm_stage=stage,
		)
		self.db_set({"stock_entry": se.name, "grey_batch": batch})
		if needs_qi:
			frappe.msgprint(
				_("Manufacture entry {0} is a draft: record the Quality Inspection, then submit it.").format(se.name),
				alert=True,
			)

	def on_cancel(self) -> None:
		if self.stock_entry and frappe.db.get_value("Stock Entry", self.stock_entry, "docstatus") == 0:
			frappe.delete_doc("Stock Entry", self.stock_entry, ignore_permissions=True)
			return
		cancel_linked("Stock Entry", self.stock_entry)
