"""Idempotent Knitting masters (Part E §E1–E4).

Run after the denim and home textile masters: `bench --site <site> execute textile_mill.setup.masters_knit.run`
(`textile_mill.setup.masters.run` calls it too).
"""

import frappe

from textile_mill.setup import master_data_knit as kn
from textile_mill.setup import masters as m
from textile_mill.setup.masters_ht import add_utility_rates

KNITTERS = [f"KNITTER-{i:02d}" for i in range(1, 7)]


def run(company: str | None = None) -> None:
	company = company or m.complete_setup_if_needed()
	m.create_warehouses(company, kn.WAREHOUSES)
	m.create_parties([], kn.CUSTOMERS)
	m.create_employees(company, KNITTERS)
	m.create_qi_templates(kn.QI_TEMPLATES)
	m.create_workstations(kn.WORKSTATIONS)
	m.create_operations(kn.OPERATIONS)
	m.create_items(company, kn.ITEMS)
	create_tshirt_items(company)
	add_utility_rates(company, kn.UTILITY_RATES)
	frappe.db.commit()

	create_boms(company)
	frappe.db.commit()
	print(f"Knitting masters ready for {company}")


def create_tshirt_items(company: str) -> None:
	from erpnext.controllers.item_variant import create_variant

	if not frappe.db.exists("Item Attribute", kn.TSHIRT_ATTRIBUTE):
		m._insert({
			"doctype": "Item Attribute",
			"attribute_name": kn.TSHIRT_ATTRIBUTE,
			"item_attribute_values": [{"attribute_value": s, "abbr": s} for s in kn.TSHIRT_SIZES],
		})
	code, name, group, warehouse, sell = kn.TSHIRT_TEMPLATE
	if not frappe.db.exists("Item", code):
		m._insert({
			"doctype": "Item",
			"item_code": code,
			"item_name": name,
			"item_group": group,
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"has_variants": 1,
			"variant_based_on": "Item Attribute",
			"attributes": [{"attribute": kn.TSHIRT_ATTRIBUTE}],
			"dm_stage": "Knit Garments",
			"item_defaults": [{"company": company, "default_warehouse": f"{warehouse} - {m._abbr(company)}"}],
		})
	for size in kn.TSHIRT_SIZES:
		variant_code = f"{code}-{size}"
		if not frappe.db.exists("Item", variant_code):
			variant = create_variant(code, {kn.TSHIRT_ATTRIBUTE: size})
			variant.item_code = variant_code
			variant.flags.ignore_permissions = True
			variant.insert()
		if not frappe.db.get_value("Item", variant_code, "dm_stage"):
			frappe.db.set_value("Item", variant_code, "dm_stage", "Knit Garments")
		m.set_prices(variant_code, 0, sell)


def create_boms(company: str) -> None:
	for item, qty, rms, scraps, ops, qi in kn.BOMS:
		if item in kn.DYE_RECIPES:
			m.ensure_dye_recipe(kn.DYE_RECIPES[item])
		else:
			m.make_bom(company, item, qty, rms, scraps, ops, qi)
	template = kn.TSHIRT_TEMPLATE[0]
	for size, fabric in kn.TSHIRT_FABRIC_KG.items():
		m.make_bom(company, f"{template}-{size}", 1, [("FK-SJ-160-NAVY", fabric), *kn.TSHIRT_TRIMS], ops=kn.TSHIRT_OPS)
