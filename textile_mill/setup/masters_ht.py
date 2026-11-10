"""Idempotent Home Textile masters (Part D §D1–D5).

Run after the denim masters: `bench --site <site> execute textile_mill.setup.masters_ht.run`
(`textile_mill.setup.masters.run` calls it too).
"""

import frappe
from frappe.utils import flt

from textile_mill.setup import master_data_ht as ht
from textile_mill.setup import masters as m


def run(company: str | None = None) -> None:
	company = company or m.complete_setup_if_needed()
	m.create_warehouses(company, ht.WAREHOUSES)
	m.create_item_groups(ht.ITEM_GROUPS)
	m.create_parties(ht.SUPPLIERS, ht.CUSTOMERS)
	m.create_qi_templates(ht.QI_TEMPLATES)
	m.create_workstations(ht.WORKSTATIONS)
	m.create_operations(ht.OPERATIONS)
	m.create_items(company, ht.ITEMS)
	m.create_service_items(ht.SERVICE_ITEMS)
	set_pieces_per_kg()
	m.apply_item_qi(ht.ITEM_QI)
	create_customer_items()
	add_utility_rates(company)
	frappe.db.commit()

	create_boms(company)
	frappe.db.commit()
	print(f"Home Textile masters ready for {company}")


def set_pieces_per_kg() -> None:
	for code, weight in frappe.get_all(
		"Item", filters={"dm_target_weight_kg": [">", 0]}, fields=["name", "dm_target_weight_kg"], as_list=True
	):
		frappe.db.set_value("Item", code, "dm_pieces_per_kg", flt(1 / flt(weight), 3))


def create_customer_items() -> None:
	for item, rows in ht.CUSTOMER_ITEMS.items():
		doc = frappe.get_doc("Item", item)
		changed = False
		for customer, ref_code, ean, pcs, marks in rows:
			if not any(r.customer_name == customer for r in doc.customer_items):
				doc.append("customer_items", {"customer_name": customer, "ref_code": ref_code})
				changed = True
			if not any(r.customer == customer for r in doc.dm_label_specs):
				doc.append(
					"dm_label_specs",
					{
						"customer": customer,
						"ean_barcode": ean,
						"pcs_per_carton": pcs,
						"carton_marks": marks,
						"label_print_format": "Carton Label" if frappe.db.exists("Print Format", "Carton Label") else None,
					},
				)
				changed = True
		if changed:
			doc.flags.ignore_permissions = True
			doc.save()


def add_utility_rates(company: str, rates: list[tuple] | None = None) -> None:
	from textile_mill.constants import STAGE_COST_CENTER

	abbr = m._abbr(company)
	settings = frappe.get_single("Textile Mill Settings")
	existing = {r.stage for r in settings.utility_rates}
	for stage, rate, uom in rates or ht.UTILITY_RATES:
		if stage not in existing:
			settings.append(
				"utility_rates",
				{
					"stage": stage,
					"rate_per_output_uom": rate,
					"uom": uom,
					"cost_center": f"{STAGE_COST_CENTER[stage]} - {abbr}",
				},
			)
	settings.flags.ignore_permissions = True
	settings.save()


def create_boms(company: str) -> None:
	"""HT-BOM-1…9 in dependency order; processed terry and printed sheeting come from Dye Recipes."""
	for item, qty, rms, scraps, ops, qi in ht.BOMS:
		if item in ht.DYE_RECIPES:
			m.ensure_dye_recipe(ht.DYE_RECIPES[item])
		else:
			m.make_bom(company, item, qty, rms, scraps, ops, qi)
