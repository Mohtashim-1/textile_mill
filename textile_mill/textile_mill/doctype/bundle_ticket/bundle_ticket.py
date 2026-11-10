# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

ORDER = {"Cut": 0, "In Stitching": 1, "Stitched": 2, "Rejected": 2}


class BundleTicket(Document):
	def validate(self) -> None:
		if self.is_new():
			return
		previous = self.get_doc_before_save()
		if previous and ORDER[self.status] < ORDER[previous.status]:
			frappe.throw(_("Bundle status can only move forward ({0} → {1} not allowed).").format(previous.status, self.status))
		if previous and previous.status in ("Stitched", "Rejected") and previous.status != self.status:
			frappe.throw(_("Bundle is already {0}.").format(previous.status))
		if self.status == "Stitched" and not self.stitched_on:
			self.stitched_on = now_datetime()


def _bundle(name: str) -> "BundleTicket":
	name = (name or "").strip()
	if not frappe.db.exists("Bundle Ticket", name):
		frappe.throw(_("Bundle {0} not found.").format(name))
	doc = frappe.get_doc("Bundle Ticket", name)
	doc.check_permission("write")
	return doc


@frappe.whitelist()
def get_bundle(name: str) -> dict:
	doc = frappe.get_doc("Bundle Ticket", (name or "").strip())
	doc.check_permission("read")
	summary = work_order_summary(doc.work_order)
	return {"bundle": doc.as_dict(), "work_order": summary}


@frappe.whitelist()
def set_status(name: str, status: str, stitch_line: str | None = None, at: str | None = None) -> dict:
	if status not in ORDER:
		frappe.throw(_("Invalid status"))
	doc = _bundle(name)
	doc.status = status
	if stitch_line:
		doc.stitch_line = stitch_line
	if status == "Stitched":
		doc.stitched_on = at or now_datetime()
	doc.save()
	return {"bundle": doc.as_dict(), "work_order": work_order_summary(doc.work_order)}


def work_order_summary(work_order: str) -> dict:
	rows = frappe.get_all(
		"Bundle Ticket", filters={"work_order": work_order}, fields=["status", "qty"]
	)
	wo = frappe.db.get_value("Work Order", work_order, ["qty", "produced_qty", "status", "production_item"], as_dict=True)
	stitched = sum(r.qty for r in rows if r.status == "Stitched")
	pending = sum(1 for r in rows if r.status in ("Cut", "In Stitching"))
	return {
		"name": work_order,
		"item": wo.production_item,
		"qty": wo.qty,
		"produced_qty": wo.produced_qty,
		"status": wo.status,
		"bundles": len(rows),
		"pending_bundles": pending,
		"stitched_qty": stitched,
		"can_complete": pending == 0 and stitched > flt(wo.produced_qty),
	}


@frappe.whitelist()
def complete_work_order(work_order: str, posting_date: str | None = None, posting_time: str | None = None, silent: bool = False):
	"""Manufacture Σ stitched qty once every bundle of the Work Order is stitched or rejected."""
	from textile_mill.manufacturing import make_manufacture_entry

	frappe.has_permission("Work Order", "write", work_order, throw=True)
	summary = work_order_summary(work_order)
	if not summary["can_complete"]:
		if silent:
			return None
		frappe.throw(_("Work Order {0} still has bundles in progress.").format(work_order))
	qty = summary["stitched_qty"] - flt(summary["produced_qty"])
	cut_plan = frappe.db.get_value("Work Order", work_order, "cut_plan")
	se = make_manufacture_entry(
		work_order,
		qty,
		posting_date,
		posting_time,
		remarks=_("Stitched bundles of Cut Plan {0}").format(cut_plan),
		cut_plan=cut_plan,
	)
	if cut_plan:
		open_wos = frappe.get_all(
			"Work Order", filters={"cut_plan": cut_plan, "docstatus": 1, "status": ["not in", ["Completed", "Closed"]]}
		)
		if not open_wos:
			frappe.db.set_value("Cut Plan", cut_plan, "status", "Stitched")
	return se.name
