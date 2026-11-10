# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cint, flt

from textile_mill.manufacturing import cancel_linked, make_material_entry, pick_batches
from textile_mill.print_utils import make_sscc
from textile_mill.utils import wh

SSCC_COMPANY_PREFIX = "8960001"


def set_net_weight(item_code: str) -> float:
	"""Net kg of one set from its BOM components' target piece weights (0 when unknown)."""
	bom = frappe.db.get_value("BOM", {"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1})
	if not bom:
		return 0.0
	qty = flt(frappe.db.get_value("BOM", bom, "quantity")) or 1
	total = 0.0
	for r in frappe.get_all("BOM Item", filters={"parent": bom}, fields=["item_code", "stock_qty"]):
		total += flt(r.stock_qty) / qty * flt(frappe.get_cached_value("Item", r.item_code, "dm_target_weight_kg"))
	return flt(total, 3)


class CartonPackingList(Document):
	def validate(self) -> None:
		so = frappe.db.get_value("Sales Order", self.sales_order, ["docstatus", "customer", "company"], as_dict=True)
		if not so or so.docstatus != 1:
			frappe.throw(_("Sales Order {0} must be submitted.").format(self.sales_order))
		self.customer = so.customer
		self.company = self.company or so.company
		if not self.pcs_per_carton:
			self.pcs_per_carton = cint(
				frappe.db.get_value(
					"Customer Label Spec",
					{"parenttype": "Item", "parent": self.item_code, "customer": self.customer},
					"pcs_per_carton",
				)
			)
		if cint(self.pcs_per_carton) <= 0:
			frappe.throw(_("Set pieces per carton (or a Customer Label Spec for {0}).").format(self.customer))
		if not flt(self.net_kg_per_unit):
			self.net_kg_per_unit = set_net_weight(self.item_code)
		self.carton_item = self.carton_item or "PKG-CARTON-L"
		self.packing_warehouse = self.packing_warehouse or wh("Packing Material Store", self.company)
		self.source_warehouse = self.source_warehouse or frappe.db.get_value(
			"Item Default", {"parent": self.item_code, "company": self.company}, "default_warehouse"
		)

		for row in self.cartons:
			if row.item_code != self.item_code:
				frappe.throw(_("Carton {0}: item must be {1}.").format(row.carton_no, self.item_code))
			self.set_carton_measures(row)
		self.total_cartons = len(self.cartons)
		self.total_qty = flt(sum(flt(r.qty) for r in self.cartons), 3)
		self.total_net_kg = flt(sum(flt(r.net_kg) for r in self.cartons), 3)
		self.total_gross_kg = flt(sum(flt(r.gross_kg) for r in self.cartons), 3)
		self.total_cbm = flt(sum(flt(r.cbm) for r in self.cartons), 4)

		pending = self.pending_qty()
		if self.total_qty > pending + 0.001:
			frappe.throw(_("Packed quantity {0} exceeds the open quantity {1} on {2}.").format(
				self.total_qty, pending, self.sales_order))

	def set_carton_measures(self, row) -> None:
		row.length_cm = flt(row.length_cm) or flt(self.carton_length_cm)
		row.width_cm = flt(row.width_cm) or flt(self.carton_width_cm)
		row.height_cm = flt(row.height_cm) or flt(self.carton_height_cm)
		row.net_kg = flt(flt(row.qty) * flt(self.net_kg_per_unit), 3)
		row.gross_kg = flt(row.net_kg + flt(self.carton_tare_kg), 3)
		row.cbm = flt(row.length_cm * row.width_cm * row.height_cm / 1_000_000, 4)

	def pending_qty(self) -> float:
		ordered = frappe.db.sql(
			"""select coalesce(sum(stock_qty - delivered_qty * conversion_factor), 0) from `tabSales Order Item`
			where parent = %s and item_code = %s""",
			(self.sales_order, self.item_code),
		)[0][0]
		other = frappe.db.sql(
			"""select coalesce(sum(cpl.total_qty), 0) from `tabCarton Packing List` cpl
			where cpl.sales_order = %s and cpl.item_code = %s and cpl.docstatus = 1 and cpl.name != %s
			and not exists (select 1 from `tabDelivery Note` dn where dn.name = cpl.delivery_note and dn.docstatus = 1)""",
			(self.sales_order, self.item_code, self.name or ""),
		)[0][0]
		return flt(ordered) - flt(other)

	@frappe.whitelist()
	def generate_cartons(self) -> None:
		"""One line per carton for the open SO quantity; the last carton may be partial."""
		if self.docstatus != 0:
			frappe.throw(_("Cartons can only be generated on a draft."))
		self.cartons = []
		self.validate()
		pending = self.pending_qty()
		per = cint(self.pcs_per_carton)
		count = math.ceil(pending / per) if per else 0
		for i in range(count):
			qty = min(per, pending - i * per)
			row = self.append("cartons", {"carton_no": f"{i + 1}/{count}", "item_code": self.item_code, "qty": qty})
			self.set_carton_measures(row)
		self.save()

	def before_submit(self) -> None:
		if not self.cartons:
			frappe.throw(_("Generate cartons before submitting."))
		for row in self.cartons:
			row.sscc = row.sscc or make_sscc(SSCC_COMPANY_PREFIX, int(getseries(f"SSCC{SSCC_COMPANY_PREFIX}", 9)))

	def on_submit(self) -> None:
		if self.carton_item and self.total_cartons:
			se = make_material_entry(
				"Material Issue",
				self.company,
				[{"item_code": self.carton_item, "qty": self.total_cartons, "s_warehouse": self.packing_warehouse}],
				self.posting_date,
				frappe.utils.nowtime() if self.posting_date == frappe.utils.getdate() else "17:00:00",
				remarks=_("Cartons for packing list {0}").format(self.name),
				dm_stage="Packing",
			)
			self.db_set("material_issue", se.name)

	def on_cancel(self) -> None:
		if self.delivery_note and frappe.db.get_value("Delivery Note", self.delivery_note, "docstatus") == 1:
			frappe.throw(_("Cancel Delivery Note {0} first.").format(self.delivery_note))
		cancel_linked("Stock Entry", self.material_issue)

	@frappe.whitelist()
	def create_delivery_note(self, posting_date=None, posting_time=None) -> str:
		"""Draft Delivery Note for every packed carton, batches picked FIFO from the source warehouse."""
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		if self.docstatus != 1:
			frappe.throw(_("Submit the packing list first."))
		if self.delivery_note and frappe.db.get_value("Delivery Note", self.delivery_note, "docstatus") in (0, 1):
			return self.delivery_note
		dn = make_delivery_note(self.sales_order)
		if posting_date:
			dn.set_posting_time = 1
			dn.posting_date = posting_date
			dn.posting_time = posting_time or "12:00:00"
		so_row = next((r for r in dn.items if r.item_code == self.item_code), None)
		if not so_row:
			frappe.throw(_("{0} has nothing left to deliver on {1}.").format(self.item_code, self.sales_order))
		base = so_row.as_dict()
		for key in ("name", "idx", "parent", "parentfield", "parenttype", "doctype"):
			base.pop(key, None)
		dn.set("items", [])
		has_batch = frappe.get_cached_value("Item", self.item_code, "has_batch_no")
		lots = pick_batches(self.item_code, self.source_warehouse, self.total_qty) if has_batch else [(None, self.total_qty)]
		for batch, qty in lots:
			dn.append(
				"items",
				{**base, "qty": qty, "warehouse": self.source_warehouse, "batch_no": batch,
					"use_serial_batch_fields": 1 if batch else 0},
			)
		dn.dm_carton_packing_list = self.name
		dn.flags.ignore_permissions = True
		dn.insert()
		self.db_set("delivery_note", dn.name)
		return dn.name
