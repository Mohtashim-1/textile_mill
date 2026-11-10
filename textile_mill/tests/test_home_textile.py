"""Part D tests: GS1 SSCC / Code 128, piece weight checks, CTP grading and carton packing on the demo data."""

import math

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cint, flt

from textile_mill.print_utils import _code128_values, code128_svg, gs1_check_digit, make_sscc
from textile_mill.textile_mill.doctype.ctp_production_entry.ctp_production_entry import main_material


class TestGS1(FrappeTestCase):
	def test_check_digit(self):
		# GS1 General Specifications worked example
		self.assertEqual(gs1_check_digit("10614141123456789"), 7)

	def test_sscc(self):
		sscc = make_sscc("8960001", 42)
		self.assertEqual(len(sscc), 18)
		self.assertTrue(sscc.startswith("08960001"))
		self.assertEqual(int(sscc[-1]), gs1_check_digit(sscc[:-1]))

	def test_sscc_overflow(self):
		with self.assertRaises(frappe.ValidationError):
			make_sscc("8960001", 10**10)

	def test_code128_checksum_and_fnc1(self):
		values = _code128_values("00" + make_sscc("8960001", 1), gs1=True)
		self.assertEqual(values[0], 105)  # Start C for an all-digit payload
		self.assertEqual(values[1], 102)  # FNC1 marks GS1-128
		self.assertEqual(values[-1], 106)  # Stop
		body, check = values[:-2], values[-2]
		self.assertEqual(check, (body[0] + sum(i * v for i, v in enumerate(body[1:], start=1))) % 103)
		self.assertIn("<svg", str(code128_svg("00123456789012345675", gs1=True)))


class TestDemoWeightChecks(FrappeTestCase):
	def test_statistics_match_samples(self):
		for name in frappe.get_all("Piece Weight Check", filters={"docstatus": 1}, pluck="name"):
			doc = frappe.get_doc("Piece Weight Check", name)
			weights = [flt(s.weight_kg) for s in doc.samples]
			avg = sum(weights) / len(weights)
			self.assertEqual(doc.sample_count, len(weights))
			self.assertAlmostEqual(doc.avg_weight_kg, avg, places=3)
			self.assertAlmostEqual(doc.variance_pct, (avg - doc.target_weight_kg) / doc.target_weight_kg * 100, places=1)


class TestDemoCTP(FrappeTestCase):
	def test_planned_pieces_and_grading(self):
		entries = frappe.get_all("CTP Production Entry", filters={"docstatus": 1}, pluck="name")
		self.assertTrue(entries, "run the home textile demo first")
		for name in entries:
			doc = frappe.get_doc("CTP Production Entry", name)
			_item, per_piece = main_material(frappe.db.get_value("Work Order", doc.work_order, "bom_no"))
			issued = sum(flt(r.qty_issued) for r in doc.source_batches)
			self.assertEqual(doc.pieces_planned, math.floor(issued / per_piece + 1e-9), name)
			self.assertLessEqual(doc.pieces_a + doc.pieces_seconds, doc.pieces_cut)
			self.assertAlmostEqual(doc.ctp_yield_pct, doc.pieces_a / doc.pieces_planned * 100, places=1)
			self.assertEqual(frappe.db.get_value("Stock Entry", doc.stock_entry, "docstatus"), 1)


class TestDemoCartons(FrappeTestCase):
	def test_cartons_cover_order(self):
		lists = frappe.get_all("Carton Packing List", filters={"docstatus": 1}, pluck="name")
		self.assertTrue(lists, "run the home textile demo first")
		for name in lists:
			doc = frappe.get_doc("Carton Packing List", name)
			self.assertEqual(len(doc.cartons), math.ceil(doc.total_qty / cint(doc.pcs_per_carton)))
			self.assertEqual(sum(flt(c.qty) for c in doc.cartons), doc.total_qty)
			ssccs = [c.sscc for c in doc.cartons]
			self.assertEqual(len(set(ssccs)), len(ssccs))
			for sscc in ssccs:
				self.assertEqual(int(sscc[-1]), gs1_check_digit(sscc[:-1]))
			if doc.delivery_note:
				self.assertEqual(frappe.db.get_value("Delivery Note", doc.delivery_note, "dm_carton_packing_list"), name)
