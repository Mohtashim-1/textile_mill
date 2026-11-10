# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from textile_mill.manufacturing import cancel_linked, make_manufacture_entry, new_batch


def roll_list(rows) -> str:
	"""Roll numbers per machine for the greige batch: CK-01/R1…Rn."""
	return ", ".join(f"{r.machine}/R1-R{cint(r.rolls_produced)}" for r in rows if cint(r.rolls_produced))


class KnittingShiftProduction(Document):
	def validate(self) -> None:
		self.validate_work_order()
		for row in self.machines:
			if flt(row.kg_produced) <= 0:
				frappe.throw(_("Row {0}: enter the kg produced on {1}.").format(row.idx, row.machine))
			if not row.dia_inch or not row.gauge:
				spec = frappe.db.get_value("Item", self.production_item(), ["dm_machine_dia", "dm_gauge", "dm_stitch_length_mm"], as_dict=True)
				if spec:
					row.dia_inch = row.dia_inch or spec.dm_machine_dia
					row.gauge = row.gauge or spec.dm_gauge
					row.stitch_length_mm = row.stitch_length_mm or spec.dm_stitch_length_mm
		self.total_kg = flt(sum(flt(r.kg_produced) for r in self.machines), 3)
		self.total_rolls = sum(cint(r.rolls_produced) for r in self.machines)
		self.total_defects = sum(cint(r.defects_count) for r in self.machines)
		self.total_stop_minutes = sum(cint(r.stop_minutes) for r in self.machines)
		self.avg_efficiency_pct = (
			flt(sum(flt(r.efficiency_pct) * flt(r.kg_produced) for r in self.machines) / self.total_kg, 2) if self.total_kg else 0
		)
		if self.total_kg <= 0:
			frappe.throw(_("Total kg must be greater than zero."))

	def production_item(self) -> str | None:
		return frappe.db.get_value("Work Order", self.work_order, "production_item")

	def validate_work_order(self) -> None:
		wo = frappe.db.get_value("Work Order", self.work_order, ["docstatus", "dm_stage"], as_dict=True)
		if not wo or wo.docstatus != 1:
			frappe.throw(_("Work Order {0} must be submitted.").format(self.work_order))
		if wo.dm_stage != "Knitting":
			frappe.throw(_("Work Order {0} is not a knitting order.").format(self.work_order))

	def on_submit(self) -> None:
		item, bom = frappe.db.get_value("Work Order", self.work_order, ["production_item", "bom_no"])
		needs_qi = frappe.db.get_value("BOM", bom, "inspection_required")
		batch = new_batch(
			item,
			manufacturing_date=self.posting_date,
			dm_stage="Knitting",
			dm_roll_list=roll_list(self.machines),
			dm_source_doctype=self.doctype,
			dm_source_doc=self.name,
		)
		se = make_manufacture_entry(
			self.work_order,
			self.total_kg,
			self.posting_date,
			self.posting_time,
			fg_batch=batch,
			employee=self.supervisor,
			submit=not needs_qi,
			remarks=_("Knitting Shift Production {0}").format(self.name),
			knitting_shift_production=self.name,
			dm_stage="Knitting",
		)
		self.db_set({"stock_entry": se.name, "greige_batch": batch})
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
