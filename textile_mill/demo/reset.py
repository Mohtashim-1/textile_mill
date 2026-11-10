"""Dev-only reset of the demo journeys (Part B §11.7).

Cancels every demo transaction of the demo company in reverse creation order, deletes them,
then removes orphaned ledger rows and demo batches. Masters, BOMs and recipes are kept.
"""

import frappe
from frappe import _

from textile_mill.setup.master_data import COMPANY

DEMO_DOCTYPES = [
	"Sales Invoice",
	"Delivery Note",
	"Payment Entry",
	"Journal Entry",
	"Purchase Invoice",
	"Purchase Receipt",
	"Purchase Order",
	"Subcontracting Receipt",
	"Subcontracting Order",
	"Stock Entry",
	"Stock Reconciliation",
	"Quality Inspection",
	"Job Card",
	"Work Order",
	"Material Request",
	"Production Plan",
	"Sales Order",
	"Indigo Range Log",
	"Loom Shift Production",
	"Fabric Roll Inspection",
	"Bundle Ticket",
	"Cut Plan",
	"Utility Consumption Log",
	"Machine Downtime Log",
	"CTP Production Entry",
	"Piece Weight Check",
	"Carton Packing List",
	"Knitting Shift Production",
	"Budget",
]

LEDGERS = {"Stock Ledger Entry": "is_cancelled", "GL Entry": "is_cancelled", "Payment Ledger Entry": "delinked"}


def _demo_docs() -> list[tuple]:
	docs = []
	for doctype in DEMO_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		filters = {"company": COMPANY} if frappe.get_meta(doctype).has_field("company") else {}
		for d in frappe.get_all(doctype, filters=filters, fields=["name", "creation", "docstatus"]):
			docs.append((d.creation, doctype, d.name, d.docstatus))
	docs.sort(reverse=True)
	return docs


def _cancel_all(pending: list[tuple[str, str]]) -> None:
	"""Reverse creation order is not always dependency order (e.g. subcontracting), so retry in passes."""
	while pending:
		failed, last_error = [], None
		for doctype, name in pending:
			if frappe.db.get_value(doctype, name, "docstatus") != 1:
				continue
			frappe.db.savepoint("demo_reset")
			try:
				doc = frappe.get_doc(doctype, name)
				doc.flags.ignore_permissions = True
				doc.flags.ignore_links = True
				doc.cancel()
			except Exception as e:
				frappe.db.rollback(save_point="demo_reset")
				frappe.clear_messages()
				failed.append((doctype, name))
				last_error = e
				print(f"  retry later: {doctype} {name}: {str(e)[:160]}")
		if len(failed) == len(pending):
			raise last_error
		pending = failed


def reset_demo() -> None:
	if not frappe.conf.get("textile_mill_allow_reset"):
		frappe.throw(_("Set textile_mill_allow_reset in site_config.json to reset demo data."))

	frappe.flags.textile_demo_reset = True
	docs = _demo_docs()
	_cancel_all([(doctype, name) for _creation, doctype, name, docstatus in docs if docstatus == 1])
	for _creation, doctype, name, _docstatus in docs:
		if frappe.db.exists(doctype, name):
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, ignore_on_trash=True)

	for ledger, cancelled_flag in LEDGERS.items():
		frappe.db.sql(
			f"delete from `tab{ledger}` where company = %s and {cancelled_flag} = 1",  # noqa: S608
			COMPANY,
		)
	frappe.db.sql("delete from `tabRepost Item Valuation` where company = %s", COMPANY)
	frappe.db.sql(
		"""delete from `tabSerial and Batch Entry` where parent in
		(select name from `tabSerial and Batch Bundle` where company = %s and docstatus != 1)""",
		COMPANY,
	)
	frappe.db.sql("delete from `tabSerial and Batch Bundle` where company = %s and docstatus != 1", COMPANY)
	frappe.db.sql(
		"""delete from `tabBatch` where name not in
		(select distinct batch_no from `tabSerial and Batch Entry` where ifnull(batch_no, '') != '')
		and name not in (select distinct batch_no from `tabStock Ledger Entry` where ifnull(batch_no, '') != '')"""
	)
	frappe.db.delete("KPI Daily Snapshot")
	frappe.defaults.clear_default("textile_demo_d0", parent="__default")
	frappe.flags.textile_demo_reset = False
	print(f"Reset {len(docs)} demo documents for {COMPANY}")
