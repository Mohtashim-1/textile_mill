"""Part C tests: KPI = report value on demo data, RAG in both directions, role access, cache keys, business lines."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from textile_mill import reports_lib as rl
from textile_mill import reports_lib_ht as ht
from textile_mill.dashboards import filters as F
from textile_mill.dashboards import targets
from textile_mill.dashboards.api import _key
from textile_mill.dashboards.kpi import calculate

PERIOD = {"period": "Custom", "from_date": "2026-01-01", "to_date": "2026-12-31"}


class TestRag(FrappeTestCase):
	def test_higher_is_better(self):
		target = {"amber_threshold": 90, "red_threshold": 80}
		self.assertEqual(targets.rag(95, target), targets.GREEN)
		self.assertEqual(targets.rag(85, target), targets.AMBER)
		self.assertEqual(targets.rag(75, target), targets.RED)
		self.assertEqual(targets.rag(None, target), targets.NEUTRAL)

	def test_lower_is_better(self):
		target = {"amber_threshold": 3, "red_threshold": 5}
		self.assertEqual(targets.rag(2, target, "Lower is better"), targets.GREEN)
		self.assertEqual(targets.rag(4, target, "Lower is better"), targets.AMBER)
		self.assertEqual(targets.rag(6, target, "Lower is better"), targets.RED)

	def test_absolute_kpi(self):
		if not targets.get_target("WEIGHT_VARIANCE_PCT"):
			self.skipTest("KPI targets not seeded")
		self.assertEqual(targets.evaluate("WEIGHT_VARIANCE_PCT", -4)["status"], targets.RED)
		self.assertEqual(targets.evaluate("WEIGHT_VARIANCE_PCT", 0.5)["status"], targets.GREEN)


class TestKpiEqualsReport(FrappeTestCase):
	def setUp(self):
		self.ctx = F.parse(PERIOD)
		self.rf = {"company": self.ctx.company, "from_date": self.ctx.from_date, "to_date": self.ctx.to_date}

	def test_recovery_yield(self):
		row = next(r for r in rl.stage_yield_summary(self.rf) if r.stage == "Cotton Recycling")
		self.assertAlmostEqual(calculate("RECOVERY_YIELD", self.ctx)["value"], row.yield_pct, places=6)

	def test_ctp_yield(self):
		totals = ht.ctp_totals(self.rf)
		planned = sum(r.pieces_planned for r in totals["rows"])
		self.assertAlmostEqual(calculate("CTP_YIELD", self.ctx)["value"], totals["a"] / planned * 100, places=6)

	def test_cartons_shipped(self):
		shipped = sum(flt(r.cartons_shipped) for r in ht.shipments(self.rf))
		self.assertEqual(calculate("CARTONS_SHIPPED", self.ctx)["value"], shipped)


class TestAccessAndCache(FrappeTestCase):
	def test_guest_denied(self):
		from textile_mill.dashboards import registry

		user = frappe.session.user
		try:
			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				registry.check("finance")
		finally:
			frappe.set_user(user)

	def test_cache_key_varies(self):
		a = _key("production", F.parse({**PERIOD, "business_line": "Denim"}))
		b = _key("production", F.parse({**PERIOD, "business_line": "Knitting"}))
		c = _key("production", F.parse({**PERIOD, "business_line": "Denim", "refresh": 1}))
		self.assertNotEqual(a, b)
		self.assertEqual(a, c)


class TestBusinessLines(FrappeTestCase):
	def test_line_stages(self):
		self.assertIn("Indigo Dyeing", F.line_stages("Denim"))
		self.assertNotIn("Indigo Dyeing", F.line_stages("Home Textile"))
		self.assertIn("Set Assembly", F.line_stages("Home Textile"))
		self.assertIn("Knit Dyeing", F.line_stages("Knitting"))
		self.assertEqual(len(F.line_flows("All")), 4)
		self.assertEqual(F.parse({"business_line": "bogus"}).business_line, F.DEFAULT_LINE)
