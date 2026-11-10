# Copyright (c) 2026, Mission20 Zero and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from textile_mill.constants import DYE_PROCESS_ROUTES
from textile_mill.utils import item_rate

APPROVED = "Production Approved"
BASIS_UOM = {"per kg": "Kg", "per m": "Meter"}


class DyeRecipe(Document):
	def validate(self) -> None:
		if flt(self.base_qty_kg) <= 0:
			frappe.throw(_("Base Qty must be greater than zero."))
		if not 0 < flt(self.expected_yield_pct) <= 100:
			frappe.throw(_("Expected Yield % must be between 0 and 100."))
		if self.shade and frappe.db.get_value("Shade", self.shade, "process_type") != self.process_type:
			frappe.throw(_("Shade {0} is not a {1} shade.").format(self.shade, self.process_type))
		self.validate_basis()
		self.calculate()

	def validate_basis(self) -> None:
		"""Chemical quantities are grams per base unit: per kg of fabric/yarn, or per metre for printing."""
		self.basis_uom = self.basis_uom or "per kg"
		base_uom = frappe.get_cached_value("Item", self.base_item, "stock_uom") if self.base_item else None
		expected = BASIS_UOM.get(self.basis_uom)
		if base_uom and expected and base_uom != expected:
			frappe.throw(
				_("Basis {0} needs a base item stocked in {1}; {2} is stocked in {3}.").format(
					self.basis_uom, expected, self.base_item, base_uom
				)
			)

	def calculate(self) -> None:
		total = 0.0
		for row in self.chemicals:
			row.qty_for_base = flt(flt(row.g_per_kg) * flt(self.base_qty_kg) / 1000, 4)
			row.rate = item_rate(row.item_code)
			row.amount = flt(row.qty_for_base * flt(row.rate), 2)
			total += row.amount
		self.total_cost_per_kg = flt(total / flt(self.base_qty_kg), 4) if self.base_qty_kg else 0

	def on_update_after_submit(self) -> None:
		if self.workflow_state == "Obsolete" and not self.is_obsolete:
			self.db_set("is_obsolete", 1)

	@property
	def output_qty(self) -> float:
		return flt(flt(self.base_qty_kg) * flt(self.expected_yield_pct) / 100, 1)


def is_approved(recipe: "DyeRecipe") -> bool:
	if recipe.docstatus != 1 or recipe.is_obsolete:
		return False
	has_workflow = frappe.db.exists("Workflow", {"document_type": "Dye Recipe", "is_active": 1})
	return recipe.workflow_state == APPROVED if has_workflow else True


@frappe.whitelist()
def create_bom(recipe: str) -> str:
	"""Generate the default BOM for an approved recipe (Part B §6.3). Returns the BOM name."""
	doc = frappe.get_doc("Dye Recipe", recipe)
	doc.check_permission("write")
	if not is_approved(doc):
		frappe.throw(_("Only {0} recipes can generate a BOM.").format(APPROVED))
	if doc.bom and frappe.db.get_value("BOM", doc.bom, "is_active"):
		return doc.bom

	route = DYE_PROCESS_ROUTES.get(doc.process_type, {})
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	qi_template = route.get("qi_template")
	if qi_template and not frappe.db.exists("Quality Inspection Template", qi_template):
		qi_template = None
	ops = [
		{"operation": op, "workstation": ws, "time_in_mins": mins}
		for op, ws, mins in route.get("operations", [])
		if frappe.db.exists("Operation", op) and frappe.db.exists("Workstation", ws)
	]
	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"company": company,
			"item": doc.output_item,
			"quantity": doc.output_qty,
			"is_active": 1,
			"is_default": 1,
			"with_operations": 1 if ops else 0,
			"rm_cost_as_per": "Valuation Rate",
			"inspection_required": 1 if qi_template else 0,
			"quality_inspection_template": qi_template,
			"dye_recipe": doc.name,
			"items": [{"item_code": doc.base_item, "qty": doc.base_qty_kg}]
			+ [{"item_code": r.item_code, "qty": r.qty_for_base} for r in doc.chemicals],
			"operations": ops,
		}
	)
	bom.insert()
	bom.submit()
	doc.db_set("bom", bom.name)
	return bom.name
