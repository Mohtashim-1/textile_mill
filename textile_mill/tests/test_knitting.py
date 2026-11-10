"""Part E tests: Knitting Shift Production and knit dyeing machine load on the demo data."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from textile_mill.overrides.work_order import KNIT_DYE_BATCH_KG
from textile_mill.textile_mill.doctype.knitting_shift_production.knitting_shift_production import roll_list


class TestRollList(FrappeTestCase):
	def test_format(self):
		rows = [frappe._dict(machine="CK-01", rolls_produced=2), frappe._dict(machine="CK-02", rolls_produced=0)]
		self.assertEqual(roll_list(rows), "CK-01/R1-R2")


class TestDemoKnitting(FrappeTestCase):
	def test_shift_totals_post_manufacture(self):
		shifts = frappe.get_all("Knitting Shift Production", filters={"docstatus": 1}, pluck="name")
		self.assertTrue(shifts, "run the knitting demo first")
		for name in shifts:
			doc = frappe.get_doc("Knitting Shift Production", name)
			self.assertAlmostEqual(doc.total_kg, sum(flt(r.kg_produced) for r in doc.machines), places=3)
			fg = frappe.db.get_value("Stock Entry Detail", {"parent": doc.stock_entry, "is_finished_item": 1}, ["transfer_qty", "batch_no"])
			self.assertAlmostEqual(flt(fg[0]), doc.total_kg, places=3)
			self.assertEqual(fg[1], doc.greige_batch)
			self.assertTrue(frappe.db.get_value("Batch", doc.greige_batch, "dm_roll_list"))

	def test_machine_load(self):
		for wo in frappe.get_all("Work Order", filters={"dm_stage": "Knit Dyeing", "docstatus": 1}, fields=["qty", "machine_load_pct"]):
			self.assertAlmostEqual(wo.machine_load_pct, wo.qty / KNIT_DYE_BATCH_KG * 100, places=1)
