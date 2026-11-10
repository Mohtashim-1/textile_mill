# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from textile_mill.utils import stage_cost_center


class UtilityConsumptionLog(Document):
	def validate(self) -> None:
		if getdate(self.period_to) < getdate(self.period_from):
			frappe.throw(_("Period To cannot be before Period From."))
		for row in self.lines:
			row.cost_center = row.cost_center or stage_cost_center(row.stage, self.company)
			row.amount = flt(flt(row.qty) * flt(row.rate), 2)
		self.total_amount = flt(sum(flt(r.amount) for r in self.lines), 2)
