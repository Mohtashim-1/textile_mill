"""Stock Entry hooks: stage tagging, utility absorption, cost center and plant (Part B §8.2)."""

import frappe
from frappe.utils import flt

from textile_mill.constants import UTILITY_ABSORBED_PREFIX
from textile_mill.utils import get_settings, stage_cost_center, stage_plant


def before_validate(doc, method=None) -> None:
	stage = resolve_stage(doc)
	if stage:
		doc.dm_stage = stage

	cost_center = stage_cost_center(stage, doc.company)
	if cost_center:
		for row in doc.items:
			row.cost_center = cost_center

	if doc.purpose == "Manufacture":
		absorb_utilities(doc, stage)

	set_base_amounts(doc)
	set_plant(doc, stage)


def resolve_stage(doc) -> str | None:
	if doc.get("dm_stage"):
		return doc.dm_stage
	if doc.work_order:
		return frappe.db.get_value("Work Order", doc.work_order, "dm_stage")
	if doc.get("cut_plan"):
		return "Garments"
	return None


def absorb_utilities(doc, stage: str | None) -> None:
	"""Append (or refresh) exactly one 'Utilities (absorbed) <stage>' additional cost row."""
	settings = get_settings()
	if not (settings.utility_absorption_enabled and settings.utility_absorbed_account and stage):
		return
	rate = next((flt(r.rate_per_output_uom) for r in settings.utility_rates if r.stage == stage), 0)
	if not rate:
		return
	fg_qty = sum(flt(r.transfer_qty or r.qty) for r in doc.items if r.is_finished_item)
	if not fg_qty:
		return

	description = f"{UTILITY_ABSORBED_PREFIX} {stage}"
	rows = [r for r in doc.additional_costs if (r.description or "").startswith(UTILITY_ABSORBED_PREFIX)]
	for extra in rows[1:]:
		doc.remove(extra)
	row = rows[0] if rows else doc.append("additional_costs", {})
	row.update(
		{
			"expense_account": settings.utility_absorbed_account,
			"description": description,
			"amount": flt(rate * fg_qty, 2),
		}
	)


def set_base_amounts(doc) -> None:
	"""Server-built entries never get base_amount (v15 only sets it client-side)."""
	for row in doc.additional_costs:
		row.exchange_rate = flt(row.exchange_rate) or 1
		row.base_amount = flt(flt(row.amount) * row.exchange_rate, 2)


def set_plant(doc, stage: str | None) -> None:
	if not doc.meta.has_field("plant") or doc.get("plant"):
		return
	doc.plant = stage_plant(stage) or default_plant(doc.company)


def default_plant(company: str) -> str | None:
	dim = frappe.db.get_value("Accounting Dimension", {"document_type": "Mill Plant"})
	if not dim:
		return None
	return frappe.db.get_value(
		"Accounting Dimension Detail", {"parent": dim, "company": company}, "default_dimension"
	)
