# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


def _in_range(value, low, high) -> bool:
	"""A reading is in spec when inside [low, high]; unset limits are ignored."""
	if value in (None, ""):
		return True
	if low not in (None, 0, 0.0) and flt(value) < flt(low):
		return False
	if high not in (None, 0, 0.0) and flt(value) > flt(high):
		return False
	return True


class IndigoRangeLog(Document):
	def validate(self) -> None:
		if self.work_order and not self.dye_recipe:
			self.dye_recipe = frappe.db.get_value("Work Order", self.work_order, "dye_recipe")
		self.evaluate()

	def evaluate(self) -> None:
		limits = (
			frappe.db.get_value(
				"Dye Recipe",
				self.dye_recipe,
				["ph_min", "ph_max", "redox_min_mv", "redox_max_mv", "indigo_g_l_min", "indigo_g_l_max"],
				as_dict=True,
			)
			if self.dye_recipe
			else None
		) or frappe._dict()

		out = 0
		for r in self.readings:
			r.in_spec = int(
				_in_range(r.ph, limits.ph_min, limits.ph_max)
				and _in_range(r.redox_mv, limits.redox_min_mv, limits.redox_max_mv)
				and _in_range(r.indigo_g_l, limits.indigo_g_l_min, limits.indigo_g_l_max)
			)
			out += 0 if r.in_spec else 1

		def avg(field):
			vals = [flt(r.get(field)) for r in self.readings if r.get(field) not in (None, "")]
			return flt(sum(vals) / len(vals), 3) if vals else 0

		self.avg_ph = avg("ph")
		self.avg_indigo_g_l = avg("indigo_g_l")
		self.avg_hydro_g_l = avg("hydro_g_l")
		self.avg_redox_mv = avg("redox_mv")
		self.out_of_spec_count = out
		self.status = "Out of Spec" if out else "In Spec"

	def on_submit(self) -> None:
		if self.status == "Out of Spec" and self.work_order:
			frappe.get_doc("Work Order", self.work_order).add_comment(
				"Comment",
				_("Indigo Range Log {0} (shift {1}): {2} reading(s) out of spec.").format(
					frappe.utils.get_link_to_form(self.doctype, self.name), self.shift, self.out_of_spec_count
				),
			)
