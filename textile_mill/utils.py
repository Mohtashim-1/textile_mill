"""Small shared helpers (company-aware names, stage lookups, rates)."""

import frappe
from frappe.utils import flt

from textile_mill.constants import STAGE_COST_CENTER, STAGE_PLANT


def get_settings():
	return frappe.get_cached_doc("Textile Mill Settings")


def default_company() -> str:
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)


def abbr(company: str | None = None) -> str:
	return frappe.get_cached_value("Company", company or default_company(), "abbr")


def wh(name: str, company: str | None = None) -> str:
	"""`wh("Yarn Store")` -> "Yarn Store - DDM"."""
	return f"{name} - {abbr(company)}"


def stage_cost_center(stage: str | None, company: str | None = None) -> str | None:
	if not stage or stage not in STAGE_COST_CENTER:
		return None
	name = f"{STAGE_COST_CENTER[stage]} - {abbr(company)}"
	return name if frappe.db.exists("Cost Center", name) else None


def stage_plant(stage: str | None) -> str | None:
	plant = STAGE_PLANT.get(stage or "")
	return plant if plant and frappe.db.exists("Mill Plant", plant) else None


def item_rate(item_code: str, warehouse: str | None = None) -> float:
	"""Best available unit cost: bin valuation, then item valuation rate, then buying price."""
	filters = {"item_code": item_code, "actual_qty": [">", 0]}
	if warehouse:
		filters["warehouse"] = warehouse
	bins = frappe.get_all("Bin", filters=filters, fields=["actual_qty", "stock_value"])
	qty = sum(flt(b.actual_qty) for b in bins)
	if qty > 0:
		return flt(sum(flt(b.stock_value) for b in bins) / qty, 4)
	rate = flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
	if rate:
		return rate
	return flt(
		frappe.db.get_value("Item Price", {"item_code": item_code, "buying": 1}, "price_list_rate")
	)


def batch_balance(batch_no: str, warehouse: str | None = None) -> float:
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	return flt(get_batch_qty(batch_no=batch_no, warehouse=warehouse) if warehouse else get_batch_qty(batch_no))


def make_batch(batch_id: str, item_code: str, **custom) -> str:
	"""Create (or reuse) a Batch with a fixed id and textile custom fields."""
	if not frappe.db.exists("Batch", batch_id):
		frappe.get_doc({"doctype": "Batch", "batch_id": batch_id, "item": item_code, **custom}).insert(
			ignore_permissions=True
		)
	elif custom:
		frappe.db.set_value("Batch", batch_id, custom)
	return batch_id
