"""Part B §13 tests 3–6: Dye Recipe, Loom Shift Production, Cut Plan, utility absorption.

Writes happen inside the test transaction and are rolled back by FrappeTestCase.
"""

import math

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cint, flt

from textile_mill.constants import UTILITY_ABSORBED_PREFIX
from textile_mill.overrides.stock_entry import absorb_utilities
from textile_mill.textile_mill.doctype.loom_shift_production.loom_shift_production import theoretical_meters


class TestDyeRecipe(FrappeTestCase):
	def test_qty_for_base(self):
		doc = frappe.get_doc({
			"doctype": "Dye Recipe", "recipe_title": "Test", "process_type": "Fiber Dyeing", "base_item": "RF-PRE-A",
			"base_qty_kg": 500, "expected_yield_pct": 97, "chemicals": [{"item_code": "CHM-SBLK", "g_per_kg": 60}],
		})
		doc.calculate()
		self.assertEqual(doc.chemicals[0].qty_for_base, 30)
		self.assertEqual(doc.output_qty, 485)

	def test_create_bom_requires_approval(self):
		from textile_mill.textile_mill.doctype.dye_recipe.dye_recipe import create_bom

		doc = frappe.get_doc({
			"doctype": "Dye Recipe", "recipe_title": "Test draft", "process_type": "Fiber Dyeing", "base_item": "RF-PRE-A",
			"output_item": "DF-BLK", "base_qty_kg": 100, "expected_yield_pct": 97,
			"chemicals": [{"item_code": "CHM-SBLK", "g_per_kg": 60}],
		})
		doc.flags.ignore_permissions = True
		doc.insert(set_name="_TEST-DR-DRAFT")
		with self.assertRaises(frappe.ValidationError):
			create_bom(doc.name)

	def test_basis_uom_must_match_base_item(self):
		doc = frappe.get_doc({"doctype": "Dye Recipe", "basis_uom": "per m", "base_item": "GT-500"})
		with self.assertRaises(frappe.ValidationError):
			doc.validate_basis()


class TestLoomShift(FrappeTestCase):
	def test_theoretical_meters(self):
		# 500 rpm × 60 × 8 h × 85 % ÷ (44 ppi × 39.37)
		self.assertAlmostEqual(theoretical_meters(500, 85, 44, 8), round(500 * 60 * 8 * 0.85 / (44 * 39.37), 2))
		self.assertEqual(theoretical_meters(0, 85, 44), 0.0)

	def test_demo_shift_matches_manufacture(self):
		for name, total, se, loom_type in frappe.get_all("Loom Shift Production", filters={"docstatus": 1},
				fields=["name", "total_meters", "stock_entry", "loom_type"], as_list=True):
			fg = frappe.db.get_value("Stock Entry Detail", {"parent": se, "is_finished_item": 1}, "sum(transfer_qty)")
			doc = frappe.get_doc("Loom Shift Production", name)
			self.assertAlmostEqual(flt(fg), doc.output_qty, places=2, msg=f"{name} ({loom_type})")


class TestCutPlan(FrappeTestCase):
	def test_pieces_and_fabric(self):
		cp = frappe.get_doc({
			"doctype": "Cut Plan", "company": frappe.db.get_single_value("Global Defaults", "default_company"),
			"style_template": "JNS-SLIM-UW", "fabric_item": "FF-DM1150-A", "marker_length_m": 5.2, "plies": 40,
			"end_bit_allowance_pct": 2, "size_ratio": [{"size": "30", "ratio": 1}, {"size": "32", "ratio": 2}],
		})
		cp.validate()
		self.assertEqual([r.pieces for r in cp.size_ratio], [40, 80])
		self.assertEqual(cp.total_pieces, 120)
		self.assertEqual(cp.fabric_uom, "Meter")
		self.assertAlmostEqual(cp.fabric_required_m, 5.2 * 40 * 1.02, places=3)

	def test_knit_marker_in_kg(self):
		cp = frappe.get_doc({
			"doctype": "Cut Plan", "company": frappe.db.get_single_value("Global Defaults", "default_company"),
			"style_template": "TSH-CREW-NAVY", "fabric_item": "FK-SJ-160-NAVY", "marker_length_m": 4.7, "plies": 10,
			"size_ratio": [{"size": "S", "ratio": 1}, {"size": "M", "ratio": 2}],
		})
		cp.validate()
		self.assertEqual(cp.fabric_uom, "Kg")
		self.assertAlmostEqual(cp.marker_qty_per_ply(), 4.7 * 72 * 0.0254 * 160 / 1000, places=6)
		self.assertEqual(cp.stores()[0], "Finished Knit Store")

	def test_demo_bundles_and_work_orders(self):
		for cp in frappe.get_all("Cut Plan", filters={"docstatus": 1}, pluck="name"):
			doc = frappe.get_doc("Cut Plan", cp)
			expected = sum(math.ceil(cint(r.pieces) / cint(doc.bundle_size)) for r in doc.size_ratio)
			self.assertEqual(frappe.db.count("Bundle Ticket", {"cut_plan": cp}), expected)
			self.assertEqual(frappe.db.count("Work Order", {"cut_plan": cp, "docstatus": 1}), len(doc.size_ratio))
			self.assertAlmostEqual(sum(flt(r.issued_m) for r in doc.fabric_rolls), doc.fabric_issued_m, places=3)


class TestUtilityAbsorption(FrappeTestCase):
	def test_single_row_after_revalidation(self):
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.append("items", {"item_code": "GT-500", "qty": 100, "transfer_qty": 100, "is_finished_item": 1})
		absorb_utilities(se, "Terry Weaving")
		absorb_utilities(se, "Terry Weaving")
		rows = [r for r in se.additional_costs if (r.description or "").startswith(UTILITY_ABSORBED_PREFIX)]
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].amount, 3000)

	def test_demo_entries_have_at_most_one_row(self):
		dupes = frappe.db.sql(
			"""select parent from `tabLanded Cost Taxes and Charges` where parenttype = 'Stock Entry'
			and description like %s group by parent having count(*) > 1""",
			f"{UTILITY_ABSORBED_PREFIX}%",
		)
		self.assertFalse(dupes)
