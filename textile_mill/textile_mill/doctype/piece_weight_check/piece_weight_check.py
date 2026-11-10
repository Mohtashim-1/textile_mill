# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import re
import statistics

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


def area_m2(size_cm: str | None) -> float:
	"""'70x140' (cm) -> 0.98 m²; 0 when the size cannot be parsed."""
	numbers = [flt(n) for n in re.findall(r"\d+(?:\.\d+)?", size_cm or "")]
	return flt(numbers[0] * numbers[1] / 10000, 6) if len(numbers) >= 2 else 0.0


def weight_result(variance_pct: float, tolerance_pct: float) -> str:
	if variance_pct > tolerance_pct:
		return "Overweight"
	if variance_pct < -tolerance_pct:
		return "Underweight"
	return "Pass"


class PieceWeightCheck(Document):
	def validate(self) -> None:
		item = frappe.get_cached_value(
			"Item", self.item_code, ["dm_target_weight_kg", "dm_weight_tolerance_pct", "dm_size_cm"], as_dict=True
		)
		self.target_weight_kg = flt(self.target_weight_kg) or flt(item.dm_target_weight_kg)
		if self.tolerance_pct in (None, ""):
			self.tolerance_pct = flt(item.dm_weight_tolerance_pct) or 5
		if self.target_weight_kg <= 0:
			frappe.throw(_("Set a target weight on item {0} or on this check.").format(self.item_code))

		weights = [flt(r.weight_kg) for r in self.samples]
		if any(w <= 0 for w in weights):
			frappe.throw(_("Every sample needs a weight above zero."))
		for i, row in enumerate(self.samples, start=1):
			row.sample_no = row.sample_no or i

		self.sample_count = len(weights)
		self.avg_weight_kg = flt(statistics.fmean(weights), 4) if weights else 0
		self.min_weight_kg = min(weights, default=0)
		self.max_weight_kg = max(weights, default=0)
		stdev = statistics.stdev(weights) if len(weights) > 1 else 0
		self.cv_pct = flt(stdev / self.avg_weight_kg * 100, 2) if self.avg_weight_kg else 0
		self.variance_pct = flt((self.avg_weight_kg - self.target_weight_kg) / self.target_weight_kg * 100, 2)
		self.result = weight_result(self.variance_pct, flt(self.tolerance_pct))
		area = area_m2(item.dm_size_cm)
		self.implied_gsm = flt(self.avg_weight_kg * 1000 / area, 1) if area else 0

	def before_submit(self) -> None:
		if self.sample_count < 1:
			frappe.throw(_("Record at least one sample before submitting."))
