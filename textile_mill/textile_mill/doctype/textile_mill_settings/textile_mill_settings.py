# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class TextileMillSettings(Document):
	def validate(self) -> None:
		if flt(self.grade_a_max_points) <= 0 or flt(self.grade_b_max_points) <= flt(self.grade_a_max_points):
			frappe.throw(_("Grade B max points must be greater than Grade A max points, and both above zero."))
		if self.default_bundle_size is not None and self.default_bundle_size < 1:
			frappe.throw(_("Default bundle size must be at least 1."))
		self._no_duplicates("utility_rates", ("stage",), _("Utility rate for stage {0} is listed twice."))
		self._no_duplicates("grade_items", ("lot_item", "grade"), _("Grade mapping {0} is listed twice."))

	def _no_duplicates(self, table: str, keys: tuple[str, ...], message: str) -> None:
		seen = set()
		for row in self.get(table):
			key = tuple(row.get(k) for k in keys)
			if key in seen:
				frappe.throw(message.format(" / ".join(map(str, key))))
			seen.add(key)


def get_settings() -> "TextileMillSettings":
	"""Cached Textile Mill Settings document."""
	return frappe.get_cached_doc("Textile Mill Settings")
