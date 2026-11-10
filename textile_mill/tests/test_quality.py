"""Part B §13 tests 1–2 (points & grading, repack valuation) and Part D piece-weight helpers."""

from frappe.tests.utils import FrappeTestCase

from textile_mill.textile_mill.doctype.fabric_roll_inspection.fabric_roll_inspection import (
	allocate_by_relative_value,
	defect_points,
	grade_for,
	points_per_100_sq_yd,
)
from textile_mill.textile_mill.doctype.piece_weight_check.piece_weight_check import area_m2, weight_result


class TestFourPointGrading(FrappeTestCase):
	def test_points_and_grade(self):
		points = sum(defect_points(length) for length in (2, 5, 8, 10)) + defect_points(1, is_hole=True)
		self.assertEqual(points, 14)
		per_100 = points_per_100_sq_yd(points, 100, 64)
		self.assertAlmostEqual(per_100, 7.20, places=2)
		self.assertEqual(grade_for(per_100, 20, 28), "A")
		self.assertEqual(grade_for(25, 20, 28), "B")
		self.assertEqual(grade_for(30, 20, 28), "Rejected")

	def test_zero_size_roll(self):
		self.assertEqual(points_per_100_sq_yd(10, 0, 64), 0.0)


class TestRelativeValueRepack(FrappeTestCase):
	def test_split_matches_source_exactly(self):
		a, b = allocate_by_relative_value(1_000_000, [(90, 1100), (10, 700)])
		self.assertAlmostEqual(a, 1_000_000 * 99_000 / 106_000, places=1)
		self.assertEqual(round(a + b, 2), 1_000_000)

	def test_no_value(self):
		self.assertEqual(allocate_by_relative_value(500, [(0, 0), (0, 0)]), [0.0, 0.0])


class TestPieceWeight(FrappeTestCase):
	def test_area(self):
		self.assertAlmostEqual(area_m2("70x140"), 0.98)
		self.assertEqual(area_m2("n/a"), 0.0)

	def test_result_band(self):
		self.assertEqual(weight_result(1.4, 5), "Pass")
		self.assertEqual(weight_result(5.1, 5), "Overweight")
		self.assertEqual(weight_result(-5.1, 5), "Underweight")
