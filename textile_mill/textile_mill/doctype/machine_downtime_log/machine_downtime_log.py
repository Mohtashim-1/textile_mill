# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, getdate, time_diff_in_seconds


class MachineDowntimeLog(Document):
	def validate(self):
		if get_datetime(self.to_time) <= get_datetime(self.from_time):
			frappe.throw(_("To Time must be after From Time."))
		self.duration_min = flt(time_diff_in_seconds(self.to_time, self.from_time) / 60, 1)
		if not self.posting_date:
			self.posting_date = getdate(self.from_time)
		self.stage = frappe.db.get_value("Workstation", self.workstation, "dm_stage") or self.stage
		self.is_planned = frappe.db.get_value("Downtime Reason", self.reason, "is_planned") or 0
		self.validate_overlap()

	def validate_overlap(self):
		overlap = frappe.db.sql(
			"""select name from `tabMachine Downtime Log` where workstation = %s and docstatus < 2 and name != %s
			and from_time < %s and to_time > %s limit 1""",
			(self.workstation, self.name or "", self.to_time, self.from_time),
		)
		if overlap:
			frappe.throw(_("Overlaps downtime {0} on {1}.").format(overlap[0][0], self.workstation))
