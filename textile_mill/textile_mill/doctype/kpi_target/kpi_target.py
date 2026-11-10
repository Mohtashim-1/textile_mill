# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class KPITarget(Document):
	def validate(self):
		direction = frappe.db.get_value("KPI Definition", self.kpi, "direction")
		target, amber, red = flt(self.target_value), flt(self.amber_threshold), flt(self.red_threshold)
		if direction == "Lower is better":
			if not target <= amber <= red:
				frappe.throw(_("For a lower-is-better KPI use Target ≤ Amber ≤ Red."))
		elif not target >= amber >= red:
			frappe.throw(_("For a higher-is-better KPI use Target ≥ Amber ≥ Red."))
