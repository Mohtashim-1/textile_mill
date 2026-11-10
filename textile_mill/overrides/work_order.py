"""Work Order hooks (Part B §8.3, Part E §E6)."""

import frappe
from frappe import _
from frappe.utils import flt

from textile_mill.textile_mill.doctype.dye_recipe.dye_recipe import is_approved

# Rated batch capacity (kg) for knit dyeing machines (Part E §E3: 1,000 kg jets).
KNIT_DYE_BATCH_KG = 1000


def before_validate(doc, method=None) -> None:
	# Only the Work Order form script fetches BOM operations; server-built orders need them too.
	if doc.docstatus == 0 and doc.bom_no and not doc.operations:
		if frappe.db.get_value("BOM", doc.bom_no, "with_operations"):
			doc.set_work_order_operations()


def validate(doc, method=None) -> None:
	stage = frappe.db.get_value("Item", doc.production_item, "dm_stage")
	if stage and stage not in ("Raw", "Waste"):
		doc.dm_stage = stage

	if doc.dye_recipe:
		recipe = frappe.get_doc("Dye Recipe", doc.dye_recipe)
		if not is_approved(recipe):
			frappe.throw(_("Dye Recipe {0} is not Production Approved.").format(doc.dye_recipe))
		if recipe.bom and doc.bom_no != recipe.bom:
			frappe.throw(_("BOM must be {0}, generated from Dye Recipe {1}.").format(recipe.bom, recipe.name))
	elif doc.bom_no:
		recipe = frappe.db.get_value("BOM", doc.bom_no, "dye_recipe")
		if recipe:
			doc.dye_recipe = recipe

	if doc.dm_stage == "Knit Dyeing":
		doc.machine_load_pct = flt(flt(doc.qty) / KNIT_DYE_BATCH_KG * 100, 1)
