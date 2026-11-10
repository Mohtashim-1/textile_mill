"""Part B §13 test 7 and Part G definition of done: traces from shipped goods back to raw-material suppliers."""

import frappe
from frappe.tests.utils import FrappeTestCase


def trace(delivery_note: str) -> list[dict]:
	from frappe.desk.query_report import run

	return run("Batch Genealogy", filters={"delivery_note": delivery_note, "max_depth": 14})["result"]


def delivery_of(item_like: str) -> str | None:
	rows = frappe.db.sql(
		"""select dni.parent from `tabDelivery Note Item` dni join `tabDelivery Note` dn on dn.name = dni.parent
		where dn.docstatus = 1 and dni.item_code like %s order by dn.posting_date limit 1""",
		item_like,
	)
	return rows[0][0] if rows else None


class TestGenealogy(FrappeTestCase):
	def assert_reaches(self, item_like: str, raw_item: str, supplier: str):
		dn = delivery_of(item_like)
		if not dn:
			self.skipTest(f"no delivery of {item_like} in the demo data")
		rows = trace(dn)
		self.assertTrue(any((r.get("item_code") or "") == raw_item for r in rows), f"{dn} does not reach {raw_item}")
		self.assertTrue(any(r.get("node_type") == "Supplier" and r.get("party") == supplier for r in rows))

	def test_jeans_to_cotton_waste_supplier(self):
		self.assert_reaches("JNS-SLIM-SW-%", "CW-PRE", "Karachi Textile Waste Traders")

	def test_towel_set_to_virgin_cotton_supplier(self):
		self.assert_reaches("TWL-SET-3PC", "VC-RAW", "Sindh Cotton Ginners")

	def test_tshirt_to_virgin_cotton_supplier(self):
		self.assert_reaches("TSH-CREW-NAVY-%", "VC-RAW", "Sindh Cotton Ginners")
