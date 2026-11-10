"""Idempotent master data for the denim vertical (Part B §3–4, Phase 1–2).

Run: `bench --site <site> execute textile_mill.setup.masters.run`
Re-running never duplicates records: every create is guarded by `frappe.db.exists`.
"""

import frappe
from frappe.utils import flt

from textile_mill.constants import COST_CENTERS, PLANTS
from textile_mill.setup import master_data as md


def run() -> None:
	"""Phase 1 + Phase 2 masters (denim)."""
	company = complete_setup_if_needed()
	frappe.flags.textile_company = company

	create_plants_and_dimension(company)
	create_cost_centers(company)
	create_accounts(company)
	create_warehouses(company, md.WAREHOUSES)
	create_uoms(md.UOMS)
	create_item_groups(md.ITEM_GROUPS)
	create_simple_masters()
	create_parties(md.SUPPLIERS, md.CUSTOMERS)
	create_employees(company, md.EMPLOYEES)
	create_qi_templates(md.QI_TEMPLATES)
	create_workstations(md.WORKSTATIONS)
	create_operations(md.OPERATIONS)
	create_items(company, md.ITEMS)
	create_service_items(md.SERVICE_ITEMS)
	copy_textile_fields_to_variants()
	create_garment_items(company)
	apply_item_qi(md.ITEM_QI)
	configure_settings(company)
	frappe.db.commit()

	create_boms(company)
	frappe.db.commit()

	from textile_mill.setup import masters_ht, masters_knit

	masters_ht.run(company)
	masters_knit.run(company)

	from textile_mill.dashboards.seed import seed_kpis

	seed_kpis()
	frappe.db.commit()
	print(f"Textile Mill masters ready for {company}")


# ---------------------------------------------------------------- company
def complete_setup_if_needed() -> str:
	"""Run the ERPNext setup wizard once (Pakistan, PKR, Jul–Jun fiscal year)."""
	company = frappe.db.get_value("Company", {"company_name": md.COMPANY}) or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if company:
		return company

	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	setup_complete(
		{
			"language": "English",
			"country": "Pakistan",
			"timezone": "Asia/Karachi",
			"currency": "PKR",
			"full_name": "Administrator",
			"email": "admin@example.com",
			"company_name": md.COMPANY,
			"company_abbr": md.ABBR,
			"chart_of_accounts": "Standard",
			"fy_start_date": "2026-07-01",
			"fy_end_date": "2027-06-30",
			"setup_demo": 0,
		}
	)
	return md.COMPANY


def _abbr(company: str) -> str:
	return frappe.get_cached_value("Company", company, "abbr")


def _insert(doc: dict, name: str | None = None):
	d = frappe.get_doc(doc)
	d.flags.ignore_permissions = True
	d.insert(set_name=name) if name else d.insert()
	return d


# ---------------------------------------------------------------- accounting
def create_plants_and_dimension(company: str, plants: tuple[str, ...] = PLANTS) -> None:
	for plant in plants:
		if not frappe.db.exists("Mill Plant", plant):
			_insert({"doctype": "Mill Plant", "plant_name": plant})

	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
		make_dimension_in_accounting_doctypes,
	)

	dim = frappe.db.get_value("Accounting Dimension", {"document_type": "Mill Plant"})
	if not dim:
		dim_doc = _insert(
			{
				"doctype": "Accounting Dimension",
				"document_type": "Mill Plant",
				"label": "Plant",
				"dimension_defaults": [
					{"company": company, "reference_document": "Mill Plant", "default_dimension": PLANTS[1]}
				],
			}
		)
	else:
		dim_doc = frappe.get_doc("Accounting Dimension", dim)
	make_dimension_in_accounting_doctypes(doc=dim_doc)

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for dt in ("Stock Entry", "Purchase Invoice", "Sales Invoice", "Journal Entry"):
		make_property_setter(dt, "plant", "reqd", "1", "Check", validate_fields_for_doctype=False)
		frappe.db.set_value(
			"Property Setter", {"doc_type": dt, "field_name": "plant", "property": "reqd"}, "module", "Textile Mill"
		)


def create_cost_centers(company: str) -> None:
	parent = frappe.db.get_value("Cost Center", {"company": company, "is_group": 1, "parent_cost_center": ["is", "not set"]})
	for cc in COST_CENTERS:
		if not frappe.db.exists("Cost Center", f"{cc} - {_abbr(company)}"):
			_insert(
				{
					"doctype": "Cost Center",
					"cost_center_name": cc,
					"parent_cost_center": parent,
					"company": company,
					"is_group": 0,
				}
			)


def create_accounts(company: str) -> None:
	abbr = _abbr(company)
	for name, parent, root_type, account_type in md.ACCOUNTS:
		if not frappe.db.exists("Account", f"{name} - {abbr}"):
			_insert(
				{
					"doctype": "Account",
					"account_name": name,
					"parent_account": f"{parent} - {abbr}",
					"company": company,
					"root_type": root_type,
					"account_type": account_type,
					"is_group": 0,
				}
			)


def create_warehouses(company: str, tree: dict[str, list[tuple[str, str]]]) -> None:
	abbr = _abbr(company)
	root = frappe.db.get_value("Warehouse", {"company": company, "is_group": 1, "parent_warehouse": ["is", "not set"]})
	for group, children in tree.items():
		group_name = f"{group} - {abbr}"
		if not frappe.db.exists("Warehouse", group_name):
			_insert(
				{
					"doctype": "Warehouse",
					"warehouse_name": group,
					"is_group": 1,
					"parent_warehouse": root,
					"company": company,
				}
			)
		for child, status in children:
			name = f"{child} - {abbr}"
			if not frappe.db.exists("Warehouse", name):
				_insert(
					{
						"doctype": "Warehouse",
						"warehouse_name": child,
						"parent_warehouse": group_name,
						"company": company,
						"dm_inventory_status": status,
					}
				)
			else:
				frappe.db.set_value("Warehouse", name, "dm_inventory_status", status)


# ---------------------------------------------------------------- stock masters
def create_uoms(uoms: dict[str, int]) -> None:
	for uom, whole in uoms.items():
		if not frappe.db.exists("UOM", uom):
			_insert({"doctype": "UOM", "uom_name": uom, "must_be_whole_number": whole})
		else:
			frappe.db.set_value("UOM", uom, "must_be_whole_number", whole)
	if not frappe.db.exists("UOM Conversion Factor", {"from_uom": "Dozen", "to_uom": "Nos"}):
		_insert({"doctype": "UOM Conversion Factor", "category": _uom_category(), "from_uom": "Dozen", "to_uom": "Nos", "value": 12})


def _uom_category() -> str:
	if not frappe.db.exists("UOM Category", "Count"):
		_insert({"doctype": "UOM Category", "category_name": "Count"})
	return "Count"


def create_item_groups(groups: list[tuple[str, str]]) -> None:
	for name, parent in groups:
		if not frappe.db.exists("Item Group", name):
			_insert({"doctype": "Item Group", "item_group_name": name, "parent_item_group": parent, "is_group": 0})


def create_simple_masters() -> None:
	for code, start, end in md.SHIFTS:
		if not frappe.db.exists("Mill Shift", code):
			_insert({"doctype": "Mill Shift", "shift_code": code, "start_time": start, "end_time": end})
	for code, name, process, color in md.SHADES:
		if not frappe.db.exists("Shade", code):
			_insert(
				{"doctype": "Shade", "shade_code": code, "shade_name": name, "process_type": process, "color_hex": color}
			)
	for code, name, category in md.DEFECT_TYPES:
		if not frappe.db.exists("Fabric Defect Type", code):
			_insert({"doctype": "Fabric Defect Type", "defect_code": code, "defect_name": name, "category": category})
	if not frappe.db.exists("Item Attribute", "Garment Size"):
		_insert(
			{
				"doctype": "Item Attribute",
				"attribute_name": "Garment Size",
				"item_attribute_values": [{"attribute_value": s, "abbr": s} for s in md.GARMENT_SIZES],
			}
		)


def create_parties(suppliers: list[tuple[str, str]], customers: list[str]) -> None:
	supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}) or "All Supplier Groups"
	for name, _kind in suppliers:
		if not frappe.db.exists("Supplier", name):
			_insert(
				{
					"doctype": "Supplier",
					"supplier_name": name,
					"supplier_group": supplier_group,
					"supplier_type": "Company",
					"country": "Pakistan",
					"is_transporter": 0,
				},
				name,
			)
	customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}) or "All Customer Groups"
	territory = frappe.db.get_value("Territory", {"is_group": 0}) or "All Territories"
	for name in customers:
		if not frappe.db.exists("Customer", name):
			_insert(
				{
					"doctype": "Customer",
					"customer_name": name,
					"customer_type": "Company",
					"customer_group": customer_group,
					"territory": territory,
				},
				name,
			)


def create_employees(company: str, codes: list[str]) -> None:
	for code in codes:
		if not frappe.db.exists("Employee", code):
			_insert(
				{
					"doctype": "Employee",
					"first_name": code,
					"employee": code,
					"company": company,
					"gender": "Male",
					"date_of_birth": "1990-01-01",
					"date_of_joining": "2024-01-01",
					"status": "Active",
				},
				code,
			)


def create_qi_templates(templates: dict[str, list[tuple[str, float, float]]]) -> None:
	for tpl, params in templates.items():
		for param, _mn, _mx in params:
			if not frappe.db.exists("Quality Inspection Parameter", param):
				_insert({"doctype": "Quality Inspection Parameter", "parameter": param})
		if not frappe.db.exists("Quality Inspection Template", tpl):
			_insert(
				{
					"doctype": "Quality Inspection Template",
					"quality_inspection_template_name": tpl,
					"item_quality_inspection_parameter": [
						{"specification": p, "numeric": 1, "min_value": mn, "max_value": mx} for p, mn, mx in params
					],
				}
			)


def create_workstations(rows: list[tuple]) -> None:
	for name, ws_type, rate, stage, rated, uom in rows:
		split = {
			"hour_rate_electricity": flt(rate * 0.40),
			"hour_rate_labour": flt(rate * 0.35),
			"hour_rate_consumable": flt(rate * 0.15),
			"hour_rate_rent": flt(rate * 0.10),
		}
		if not frappe.db.exists("Workstation Type", ws_type):
			_insert({"doctype": "Workstation Type", "workstation_type": ws_type, **split})
		values = {
			"workstation_type": ws_type,
			"dm_stage": stage,
			"dm_rated_output_per_hour": rated,
			"dm_output_uom": uom,
			"dm_planned_hours_per_day": 24,
			# Summary job cards (one per shift document) overlap in time on the same workstation.
			"production_capacity": 50,
			**split,
		}
		if not frappe.db.exists("Workstation", name):
			_insert({"doctype": "Workstation", "workstation_name": name, **values})
		else:
			frappe.db.set_value("Workstation", name, "production_capacity", 50)


def create_operations(ops: list[str]) -> None:
	for op in ops:
		if not frappe.db.exists("Operation", op):
			_insert({"doctype": "Operation", "description": op}, op)
	for op, workstation in md.CORRECTIVE_OPERATIONS:
		if not frappe.db.exists("Operation", op):
			_insert(
				{"doctype": "Operation", "description": op, "is_corrective_operation": 1, "workstation": workstation}, op
			)


def create_items(company: str, items: list[tuple]) -> None:
	abbr = _abbr(company)
	for code, name, group, uom, series, warehouse, buy, sell, stage, extra in items:
		if frappe.db.exists("Item", code):
			continue
		doc = {
			"doctype": "Item",
			"item_code": code,
			"item_name": name,
			"item_group": group,
			"stock_uom": uom,
			"is_stock_item": 1,
			"include_item_in_manufacturing": 1,
			"valuation_rate": buy,
			"dm_stage": stage,
			"item_defaults": [{"company": company, "default_warehouse": f"{warehouse} - {abbr}"}],
			**extra,
		}
		if series:
			doc.update({"has_batch_no": 1, "create_new_batch": 1, "batch_number_series": series})
		_insert(doc)
		set_prices(code, buy, sell)


def create_service_items(items: list[tuple]) -> None:
	for code, name, rate, stage in items:
		if not frappe.db.exists("Item", code):
			_insert(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": name,
					"item_group": "Services",
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_purchase_item": 1,
					"is_sales_item": 0,
					"dm_stage": stage,
				}
			)
			set_prices(code, rate, 0)


def set_prices(code: str, buy: float, sell: float) -> None:
	for price_list, rate, flag in (("Standard Buying", buy, "buying"), ("Standard Selling", sell, "selling")):
		if rate and not frappe.db.exists("Item Price", {"item_code": code, "price_list": price_list}):
			_insert({"doctype": "Item Price", "item_code": code, "price_list": price_list, "price_list_rate": rate, flag: 1})


def create_garment_items(company: str) -> None:
	from erpnext.controllers.item_variant import create_variant

	abbr = _abbr(company)
	for code, name, group, warehouse, sell, subcontracted in md.GARMENT_TEMPLATES:
		extra = {"is_sub_contracted_item": 1, "inspection_required_before_delivery": 1, "quality_inspection_template": "QIT-JNS"} if subcontracted else {}
		if not frappe.db.exists("Item", code):
			_insert(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": name,
					"item_group": group,
					"stock_uom": "Nos",
					"is_stock_item": 1,
					"has_variants": 1,
					"variant_based_on": "Item Attribute",
					"attributes": [{"attribute": "Garment Size"}],
					"dm_stage": "Garments",
					"item_defaults": [{"company": company, "default_warehouse": f"{warehouse} - {abbr}"}],
					**extra,
				}
			)
		for size in md.GARMENT_SIZES:
			variant_code = f"{code}-{size}"
			if not frappe.db.exists("Item", variant_code):
				variant = create_variant(code, {"Garment Size": size})
				variant.item_code = variant_code
				variant.update(extra)
				variant.flags.ignore_permissions = True
				variant.insert()
			if not frappe.db.get_value("Item", variant_code, "dm_stage"):
				frappe.db.set_value("Item", variant_code, "dm_stage", frappe.db.get_value("Item", code, "dm_stage"))
			set_prices(variant_code, 0, sell)


def copy_textile_fields_to_variants() -> None:
	"""Variants inherit textile attributes (stage, shade, GSM...) from their template."""
	settings = frappe.get_single("Item Variant Settings")
	present = {f.field_name for f in settings.fields}
	fields = [
		f.fieldname
		for f in frappe.get_meta("Item").fields
		if f.fieldname.startswith("dm_") and f.fieldtype not in ("Section Break", "Column Break", "Table")
	]
	missing = [f for f in fields if f not in present]
	if missing:
		for fieldname in missing:
			settings.append("fields", {"field_name": fieldname})
		settings.save()


def apply_item_qi(mapping: dict[str, tuple[str, str]]) -> None:
	for item, (tpl, when) in mapping.items():
		field = "inspection_required_before_purchase" if when == "purchase" else "inspection_required_before_delivery"
		frappe.db.set_value("Item", item, {field: 1, "quality_inspection_template": tpl})


# ---------------------------------------------------------------- settings (Part B §3.6)
def configure_settings(company: str) -> None:
	abbr = _abbr(company)
	stock = frappe.get_single("Stock Settings")
	stock.update(
		{
			"valuation_method": "Moving Average",
			"allow_negative_stock": 0,
			"use_serial_batch_fields": 1,
		}
	)
	stock.flags.ignore_permissions = True
	stock.save()

	mfg = frappe.get_single("Manufacturing Settings")
	mfg.update(
		{
			"backflush_raw_materials_based_on": "Material Transferred for Manufacture",
			"material_consumption": 1,
			"add_corrective_operation_cost_in_finished_good_valuation": 1,
			"overproduction_percentage_for_work_order": 3,
			"disable_capacity_planning": 1,
		}
	)
	mfg.flags.ignore_permissions = True
	mfg.save()

	settings = frappe.get_single("Textile Mill Settings")
	settings.utility_absorbed_account = f"Utilities Absorbed - {abbr}"
	existing_stages = {r.stage for r in settings.utility_rates}
	for stage, rate, uom in md.UTILITY_RATES:
		if stage not in existing_stages:
			settings.append(
				"utility_rates",
				{"stage": stage, "rate_per_output_uom": rate, "uom": uom, "cost_center": f"{stage} - {abbr}"},
			)
	existing_grades = {(r.lot_item, r.grade) for r in settings.grade_items}
	for lot, grade, item, warehouse, rsv in md.GRADE_MAP:
		if (lot, grade) not in existing_grades:
			settings.append(
				"grade_items",
				{
					"lot_item": lot,
					"grade": grade,
					"graded_item": item,
					"target_warehouse": f"{warehouse} - {abbr}",
					"relative_sales_value": rsv,
				},
			)
	settings.flags.ignore_permissions = True
	settings.save()


# ---------------------------------------------------------------- BOMs (Phase 2, Part B §4.8)
def make_bom(
	company: str,
	item: str,
	qty: float,
	rms: list[tuple[str, float]],
	scraps: list[tuple[str, float]] | None = None,
	ops: list[tuple[str, str, float]] | None = None,
	qi_template: str | None = None,
	**extra,
) -> str:
	"""Create + submit a default BOM unless the item already has an active default one."""
	existing = frappe.db.get_value("BOM", {"item": item, "is_default": 1, "is_active": 1, "docstatus": 1})
	if existing:
		return existing
	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"company": company,
			"item": item,
			"quantity": qty,
			"is_active": 1,
			"is_default": 1,
			"with_operations": 1 if ops else 0,
			"rm_cost_as_per": "Valuation Rate",
			"inspection_required": 1 if qi_template else 0,
			"quality_inspection_template": qi_template,
			"items": [{"item_code": rm, "qty": q} for rm, q in rms],
			"scrap_items": [{"item_code": s, "stock_qty": q} for s, q in (scraps or [])],
			"operations": [{"operation": o, "workstation": w, "time_in_mins": m} for o, w, m in (ops or [])],
			**extra,
		}
	)
	bom.flags.ignore_permissions = True
	bom.insert()
	bom.submit()
	return bom.name


def create_boms(company: str) -> None:
	"""BOM-1…BOM-9 in dependency order; dye BOMs come from approved Dye Recipes."""
	boms = {b[0]: b for b in md.BOMS}

	def plain(item):
		_, qty, rms, scraps, ops, qi = boms[item]
		return make_bom(company, item, qty, rms, scraps, ops, qi)

	plain("RF-PRE-A")
	ensure_dye_recipe(md.DYE_RECIPES[0])
	plain("YRN-W-10NE-60R")
	plain("YRN-F-16NE-BLK")
	ensure_dye_recipe(md.DYE_RECIPES[1])
	plain("GF-DM1150")
	plain("FF-DM1150")

	for size, fabric in md.JEANS_FABRIC_PER_SIZE.items():
		make_bom(
			company,
			f"JNS-SLIM-UW-{size}",
			1,
			[("FF-DM1150-A", fabric), *md.JEANS_TRIMS],
			ops=md.JEANS_OPS,
		)
	for size in md.GARMENT_SIZES:
		fg = f"JNS-SLIM-SW-{size}"
		fg_bom = make_bom(company, fg, 1, [(f"JNS-SLIM-UW-{size}", 1), ("PKG-POLY", 1)])
		make_subcontracting_bom(fg, fg_bom, "SRV-WASH")


def make_subcontracting_bom(fg: str, fg_bom: str, service_item: str) -> None:
	if frappe.db.exists("Subcontracting BOM", {"finished_good": fg, "is_active": 1}):
		return
	_insert(
		{
			"doctype": "Subcontracting BOM",
			"is_active": 1,
			"finished_good": fg,
			"finished_good_qty": 1,
			"finished_good_bom": fg_bom,
			"service_item": service_item,
			"service_item_qty": 1,
			"service_item_uom": "Nos",
		}
	)


def ensure_dye_recipe(spec: dict) -> str:
	"""Create, approve (workflow) and generate the BOM for a demo recipe. Idempotent."""
	from frappe.model.workflow import apply_workflow

	from textile_mill.textile_mill.doctype.dye_recipe.dye_recipe import create_bom

	name = spec["name"]
	if not frappe.db.exists("Dye Recipe", name):
		data = {k: v for k, v in spec.items() if k not in ("name", "chemicals")}
		_insert(
			{
				"doctype": "Dye Recipe",
				**data,
				"workflow_state": "Draft",
				"chemicals": [{"item_code": c, "g_per_kg": g} for c, g in spec["chemicals"]],
			},
			name,
		)
	doc = frappe.get_doc("Dye Recipe", name)
	while doc.workflow_state in ("Draft", "Lab Approved", None, ""):
		doc = apply_workflow(doc, "Approve")
	if not doc.bom:
		create_bom(name)
	return frappe.db.get_value("Dye Recipe", name, "bom")
