"""KPI targets and RAG evaluation (Part C §5.2, §6.1)."""

import frappe
from frappe.utils import flt, getdate

GREEN, AMBER, RED, NEUTRAL = "green", "amber", "red", "neutral"
# Signed KPIs where both directions are bad: RAG is judged on |value|.
ABS_KPIS = {"WEIGHT_VARIANCE_PCT"}


def direction(kpi: str) -> str:
	return frappe.get_cached_value("KPI Definition", kpi, "direction") or "Higher is better"


def get_target(kpi: str, stage: str | None = None, plant: str | None = None, on_date=None) -> frappe._dict | None:
	"""Most specific effective target: exact stage/plant beats blank, latest effective_from wins."""
	on_date = getdate(on_date) if on_date else getdate()
	rows = frappe.get_all(
		"KPI Target",
		filters={"kpi": kpi},
		fields=["target_value", "amber_threshold", "red_threshold", "stage", "plant", "effective_from"],
	)
	best, best_score = None, -1
	for r in rows:
		if r.effective_from and getdate(r.effective_from) > on_date:
			continue
		if (r.stage and r.stage != stage) or (r.plant and r.plant != plant):
			continue
		score = (2 if r.stage else 0) + (1 if r.plant else 0)
		if score > best_score or (score == best_score and getdate(r.effective_from or "1900-01-01") > getdate(best.effective_from or "1900-01-01")):
			best, best_score = r, score
	return best


def rag(value, target: dict | None, kpi_direction: str = "Higher is better") -> str:
	"""Thresholds are absolute values; direction decides which side is bad."""
	if value is None or not target:
		return NEUTRAL
	value = flt(value)
	amber, red = flt(target.get("amber_threshold")), flt(target.get("red_threshold"))
	if kpi_direction == "Lower is better":
		if value >= red:
			return RED
		if value >= amber:
			return AMBER
		return GREEN
	if value <= red:
		return RED
	if value <= amber:
		return AMBER
	return GREEN


def evaluate(kpi: str, value, stage: str | None = None, plant: str | None = None, on_date=None) -> dict | None:
	target = get_target(kpi, stage, plant, on_date)
	if not target:
		return None
	return {
		"value": flt(target.target_value),
		"amber": flt(target.amber_threshold),
		"red": flt(target.red_threshold),
		"status": rag(abs(flt(value)) if kpi in ABS_KPIS and value is not None else value, target, direction(kpi)),
	}
