"""Whitelisted endpoints for the director dashboards (Part C §4)."""

import hashlib
import json
import time

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from textile_mill.constants import PLANTS
from textile_mill.dashboards import filters as F
from textile_mill.dashboards import registry

CACHE_TTL = 300


def _key(dashboard: str, ctx) -> str:
	payload = {k: str(v) for k, v in ctx.items() if k != "refresh"}
	filters_hash = hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]  # noqa: S324
	roles_hash = hashlib.md5(",".join(sorted(frappe.get_roles())).encode()).hexdigest()[:8]  # noqa: S324
	return f"dm_dash:{dashboard}:{filters_hash}:{roles_hash}"


@frappe.whitelist()
def get_dashboard(dashboard: str, filters: str | dict | None = None) -> dict:
	config = registry.check(dashboard)
	ctx = F.parse(filters)
	if dashboard == "stage" and ctx.stage_slug not in F.SLUG_STAGES:
		frappe.throw(_("Choose a stage."))
	key = _key(dashboard, ctx)
	cache = frappe.cache()
	if not ctx.refresh:
		cached = cache.get_value(key)
		if cached:
			cached["meta"]["cached"] = True
			return cached
	started = time.monotonic()
	ctx.synthetic = False
	tiles, widgets = frappe.get_module(config["module"]).build(ctx)
	synthetic = bool(ctx.synthetic) or any(w.get("synthetic") for w in widgets)
	title = config["title"]
	if dashboard == "stage":
		title = f"{F.SLUG_TITLES[ctx.stage_slug]} — {_('Stage Drill-down')}"
	result = {
		"meta": {
			"dashboard": dashboard,
			"title": title,
			"company": ctx.company,
			"currency": frappe.get_cached_value("Company", ctx.company, "default_currency") if ctx.company else None,
			"period": ctx.period,
			"from_date": str(ctx.from_date),
			"to_date": str(ctx.to_date),
			"compare_to": ctx.compare_to,
			"compare_from": str(ctx.compare_from) if ctx.compare_from else None,
			"compare_until": str(ctx.compare_until) if ctx.compare_until else None,
			"generated_at": str(now_datetime()),
			"build_seconds": round(time.monotonic() - started, 2),
			"refresh_seconds": config["refresh"],
			"sample_history": synthetic,
			"cached": False,
		},
		"tiles": tiles,
		"widgets": widgets,
	}
	result = json.loads(frappe.as_json(result))
	cache.set_value(key, result, expires_in_sec=CACHE_TTL)
	return result


@frappe.whitelist()
def get_filter_options(dashboard: str | None = None) -> dict:
	if dashboard:
		registry.check(dashboard)
	companies = frappe.get_all("Company", pluck="name")
	return {
		"periods": list(F.PERIODS),
		"compare_to": list(F.COMPARE_TO),
		"default_period": F.DEFAULT_PERIOD,
		"default_compare": F.DEFAULT_COMPARE,
		"companies": companies,
		"default_company": frappe.defaults.get_user_default("Company") or (companies[0] if companies else None),
		"plants": [p for p in PLANTS if frappe.db.exists("Mill Plant", p)] or list(PLANTS),
		"stages": [{"slug": s, "title": t} for s, t in F.SLUG_TITLES.items()],
		"business_lines": list(F.BUSINESS_LINES),
		"default_line": F.DEFAULT_LINE,
		"line_dashboards": list(F.LINE_DASHBOARDS),
		"dashboards": registry.visible_dashboards(),
	}


@frappe.whitelist()
def create_material_request(item_code: str, warehouse: str, qty: float | None = None) -> str:
	if not frappe.has_permission("Material Request", "create") or "Stock Manager" not in frappe.get_roles():
		frappe.throw(_("Only a Stock Manager can raise material requests from the dashboard."), frappe.PermissionError)
	qty = flt(qty) or flt(frappe.db.get_value("Item Reorder", {"parent": item_code, "warehouse": warehouse}, "warehouse_reorder_qty")) or 1
	company = frappe.db.get_value("Warehouse", warehouse, "company")
	mr = frappe.get_doc({
		"doctype": "Material Request",
		"material_request_type": "Purchase",
		"company": company,
		"schedule_date": frappe.utils.add_days(frappe.utils.today(), 7),
		"items": [{"item_code": item_code, "qty": qty, "warehouse": warehouse, "schedule_date": frappe.utils.add_days(frappe.utils.today(), 7)}],
	})
	mr.insert()
	return mr.name
