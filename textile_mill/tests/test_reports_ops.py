"""Operational control reports (docs/REPORTS.md): every report runs, and the critical ones flag what they should."""

import frappe
from frappe.desk.query_report import run
from frappe.tests.utils import FrappeTestCase

from textile_mill import reports_lib_ops as ops

COMPANY = "Demo Textile Mills (Pvt) Ltd"
PERIOD = {"company": COMPANY, "from_date": "2026-01-01", "to_date": "2100-12-31"}
OPS_REPORTS = (
	"Yield Loss Exceptions", "Late Order Risk", "Material Shortage vs Plan", "Margin Erosion", "Aged and Stuck WIP",
	"Quality Hold", "Corrective Cost Summary", "Give-away Cost", "Downtime and MTBF", "Shift Production Register",
	"Operator Performance", "Defect Pareto", "Dye House Batch Log", "Chemical Consumption per Unit", "Utility Cost per Unit",
	"Waste and By-product Recovery", "Subcontract Reconciliation", "Marker Efficiency and Over-cut", "Bundle Line WIP",
	"Order Book by Business Line",
)


def demo_ready() -> bool:
	return bool(frappe.db.exists("Company", COMPANY) and frappe.db.count("Cut Plan", {"docstatus": 1}))


class TestOperationalReports(FrappeTestCase):
	def setUp(self):
		if not demo_ready():
			self.skipTest("demo data not loaded")

	def test_every_report_runs(self):
		for name in OPS_REPORTS:
			with self.subTest(report=name):
				result = run(name, filters=PERIOD)
				self.assertIsInstance(result["result"], list)

	def test_recall_trace_reaches_every_line(self):
		lot = frappe.db.get_value("Batch", {"item": "CW-PRE"}, "name")
		customers = {r.customer for r in ops.recall_trace({"batch_no": lot})}
		self.assertIn("Urban Threads LLC", customers)
		self.assertIn("Lahore Fashion Fabrics", customers)
		knit_customers = set()
		for lot in frappe.get_all("Batch", {"item": "VC-RAW"}, pluck="name"):
			knit_customers |= {r.customer for r in ops.recall_trace({"batch_no": lot})}
		self.assertIn("Metro Retail (Pvt) Ltd", knit_customers)

	def test_yield_exceptions_only_below_target(self):
		rows = ops.yield_exceptions(PERIOD)
		self.assertTrue(all(r.yield_pct < r.target_pct for r in rows))
		self.assertTrue(all(r.loss_value >= 0 for r in rows))

	def test_defect_pareto_is_cumulative(self):
		rows = ops.defect_pareto(PERIOD)
		self.assertTrue(rows)
		self.assertAlmostEqual(rows[-1].cumulative_pct, 100, places=6)
		self.assertEqual([r.points for r in rows], sorted((r.points for r in rows), reverse=True))

	def test_tshirt_over_cut(self):
		plan = next(p for p in ops.marker_efficiency(PERIOD) if p.style_template == "TSH-CREW-NAVY")
		self.assertEqual(plan.over_cut, 4)

	def test_corrective_cost_matches_core_report(self):
		core = sum(r.get("cost") or 0 for r in run("Corrective Report", filters=PERIOD)["result"])
		self.assertAlmostEqual(sum(r.cost for r in ops.corrective_cost_summary(PERIOD)), core, places=2)

	def test_giveaway_matches_weight_compliance(self):
		core = sum(r.get("giveaway_value") or 0 for r in run("Weight Compliance", filters=PERIOD)["result"])
		self.assertAlmostEqual(sum(r.giveaway_value for r in ops.giveaway_cost(PERIOD)), core, places=2)
