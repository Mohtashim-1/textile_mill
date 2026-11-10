# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from textile_mill.manufacturing import cancel_linked, new_batch
from textile_mill.utils import batch_balance, get_settings

YARDS_PER_M = 1.09361


def defect_points(length_inch: float, is_hole: bool = False) -> int:
	"""4-point system: ≤3" → 1; ≤6" → 2; ≤9" → 3; >9" → 4; holes always 4."""
	if is_hole:
		return 4
	length = flt(length_inch)
	if length <= 3:
		return 1
	if length <= 6:
		return 2
	if length <= 9:
		return 3
	return 4


def points_per_100_sq_yd(total_points: float, length_m: float, width_inch: float) -> float:
	length_yd = flt(length_m) * YARDS_PER_M
	if not (length_yd and width_inch):
		return 0.0
	return flt(flt(total_points) * 3600 / (length_yd * flt(width_inch)), 2)


def grade_for(points: float, a_max: float, b_max: float) -> str:
	if points <= a_max:
		return "A"
	if points <= b_max:
		return "B"
	return "Rejected"


def allocate_by_relative_value(total_value: float, rows: list[tuple[float, float]]) -> list[float]:
	"""Split `total_value` over (qty, relative_sales_value) rows; returns amounts summing exactly."""
	weights = [flt(q) * flt(v) for q, v in rows]
	denom = sum(weights)
	if not denom:
		return [0.0 for _ in rows]
	amounts = [flt(total_value * w / denom, 2) for w in weights]
	if amounts:
		amounts[-1] = flt(total_value - sum(amounts[:-1]), 2)
	return amounts


class FabricRollInspection(Document):
	def validate(self) -> None:
		settings = get_settings()
		hole_codes = set(
			frappe.get_all(
				"Fabric Defect Type", filters={"defect_name": ["like", "%hole%"]}, pluck="name"
			)
		)
		roll_nos = [r.roll_no for r in self.rolls]
		if len(roll_nos) != len(set(roll_nos)):
			frappe.throw(_("Roll numbers must be unique."))

		points = {r: 0 for r in roll_nos}
		for d in self.defects:
			if d.roll_no not in points:
				frappe.throw(_("Defect row {0}: roll {1} is not in the rolls table.").format(d.idx, d.roll_no))
			d.points = defect_points(d.defect_length_inch, d.defect_type in hole_codes)
			points[d.roll_no] += d.points

		totals = {"A": 0.0, "B": 0.0, "Rejected": 0.0}
		for r in self.rolls:
			r.width_inch = flt(r.width_inch) or flt(self.fabric_width_inch)
			r.total_points = points[r.roll_no]
			r.points_per_100_sq_yd = points_per_100_sq_yd(r.total_points, r.length_m, r.width_inch)
			r.grade = grade_for(r.points_per_100_sq_yd, flt(settings.grade_a_max_points), flt(settings.grade_b_max_points))
			totals[r.grade] += flt(r.length_m)

		if self.docstatus == 0 and self.lot_batch:
			self.lot_qty_m = batch_balance(self.lot_batch, self.source_warehouse)
		self.total_inspected_m = flt(sum(flt(r.length_m) for r in self.rolls), 3)
		self.inspection_loss_m = flt(flt(self.lot_qty_m) - self.total_inspected_m, 3)
		if self.inspection_loss_m < -0.001:
			frappe.throw(
				_("Inspected length {0} m exceeds lot balance {1} m.").format(self.total_inspected_m, self.lot_qty_m)
			)
		self.a_m, self.b_m, self.rejected_m = totals["A"], totals["B"], totals["Rejected"]
		base = self.total_inspected_m or 1
		self.a_pct = flt(self.a_m / base * 100, 2)
		self.b_pct = flt(self.b_m / base * 100, 2)
		self.rejected_pct = flt(self.rejected_m / base * 100, 2)

	def grade_map(self) -> dict:
		rows = {r.grade: r for r in get_settings().grade_items if r.lot_item == self.lot_item}
		missing = {"A", "B", "Rejected"} - set(rows)
		if missing:
			frappe.throw(
				_("Textile Mill Settings has no grade item for {0} grade(s): {1}").format(self.lot_item, ", ".join(missing))
			)
		return rows

	def on_submit(self) -> None:
		gmap = self.grade_map()
		stage = frappe.db.get_value("Item", self.lot_item, "dm_stage") or "Finishing"
		se = frappe.new_doc("Stock Entry")
		se.update(
			{
				"stock_entry_type": "Repack",
				"purpose": "Repack",
				"company": self.company,
				"set_posting_time": 1,
				"posting_date": self.inspection_date,
				"posting_time": "18:00:00",
				"fabric_roll_inspection": self.name,
				"dm_stage": stage,
				"remarks": _("Fabric Roll Inspection {0}").format(self.name),
			}
		)
		consume = flt(self.lot_qty_m) or self.total_inspected_m
		uom = frappe.get_cached_value("Item", self.lot_item, "stock_uom")
		placeholder_rate = flt(
			frappe.db.get_value("Bin", {"item_code": self.lot_item, "warehouse": self.source_warehouse}, "valuation_rate")
		)
		se.append(
			"items",
			{
				"item_code": self.lot_item,
				"s_warehouse": self.source_warehouse,
				"qty": consume,
				"transfer_qty": consume,
				"uom": uom,
				"stock_uom": uom,
				"conversion_factor": 1,
				"batch_no": self.lot_batch,
				"use_serial_batch_fields": 1,
			},
		)
		for r in self.rolls:
			g = gmap[r.grade]
			batch = new_batch(
				g.graded_item,
				batch_id=f"ROLL-{self.name}-{r.roll_no}",
				manufacturing_date=self.inspection_date,
				dm_stage=stage,
				dm_grade=r.grade,
				dm_roll_length_m=r.length_m,
				dm_width_inch=r.width_inch,
				dm_gsm=r.gsm,
				dm_roll_weight_kg=r.roll_weight_kg,
				dm_shade_group=r.shade_group,
				dm_source_doctype=self.doctype,
				dm_source_doc=self.name,
			)
			r.db_set("batch_no", batch)
			se.append(
				"items",
				{
					"item_code": g.graded_item,
					"t_warehouse": g.target_warehouse,
					"qty": r.length_m,
					"transfer_qty": r.length_m,
					"uom": uom,
					"stock_uom": uom,
					"conversion_factor": 1,
					"batch_no": batch,
					"use_serial_batch_fields": 1,
					"is_finished_item": 1,
					"set_basic_rate_manually": 1,
					"basic_rate": placeholder_rate,
					"basic_amount": placeholder_rate * flt(r.length_m),
				},
			)
		se.flags.ignore_permissions = True
		se.insert()

		# Relative sales value: source value split by length × RSV (Part B §6.6 decision).
		source_value = sum(flt(i.basic_amount) for i in se.items if i.s_warehouse)
		targets = [i for i in se.items if i.t_warehouse]
		amounts = allocate_by_relative_value(
			source_value,
			[(flt(i.transfer_qty), flt(gmap[self._grade_of(i.batch_no)].relative_sales_value)) for i in targets],
		)
		for row, amount in zip(targets, amounts):
			row.set_basic_rate_manually = 1
			row.basic_rate = flt(amount / flt(row.transfer_qty), 9)
			# ERPNext skips basic_amount for manually rated rows (the form script normally sets it).
			row.basic_amount = flt(amount, row.precision("basic_amount"))
		se.save()
		se.submit()
		self.db_set("stock_entry", se.name)

	def _grade_of(self, batch_no: str) -> str:
		return next(r.grade for r in self.rolls if r.batch_no == batch_no or f"ROLL-{self.name}-{r.roll_no}" == batch_no)

	def on_cancel(self) -> None:
		cancel_linked("Stock Entry", self.stock_entry)
