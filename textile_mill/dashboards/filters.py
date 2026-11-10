"""Dashboard filter parsing: period → (from, to) plus the comparison window (Part C §3)."""

import json

import frappe
from frappe import _
from frappe.utils import add_days, add_months, add_years, date_diff, get_first_day, get_quarter_start, getdate, today

PERIODS = ("Today", "This Week", "MTD", "QTD", "YTD", "Last 30 days", "Last 90 days", "Custom")
COMPARE_TO = ("Previous period", "Same period last year", "Target")
DEFAULT_PERIOD = "Last 30 days"
DEFAULT_COMPARE = "Previous period"
SLUG_STAGES = {
	"recycling": ("Cotton Recycling",),
	"fiber-dyeing": ("Fiber Dyeing",),
	"spinning": ("Spinning",),
	"indigo": ("Indigo Dyeing",),
	"weaving-finishing": ("Weaving", "Finishing"),
	"garments": ("Garments",),
	"terry-weaving": ("Terry Weaving",),
	"flat-weaving": ("Flat Weaving",),
	"processing": ("Processing",),
	"printing": ("Printing",),
	"cut-to-piece": ("Cut-to-Piece",),
	"packing": ("Set Assembly", "Packing"),
	"knitting": ("Knitting",),
	"knit-dyeing": ("Knit Dyeing",),
	"knit-finishing": ("Knit Finishing",),
	"knit-garments": ("Knit Garments",),
}
SLUG_TITLES = {
	"recycling": "Recycling",
	"fiber-dyeing": "Fiber Dyeing",
	"spinning": "Spinning",
	"indigo": "Indigo",
	"weaving-finishing": "Weaving & Finishing",
	"garments": "Garments",
	"terry-weaving": "Terry Weaving",
	"flat-weaving": "Flat Weaving",
	"processing": "Processing",
	"printing": "Printing",
	"cut-to-piece": "Cut-to-Piece",
	"packing": "Set Assembly & Packing",
	"knitting": "Knitting",
	"knit-dyeing": "Knit Dyeing",
	"knit-finishing": "Knit Finishing",
	"knit-garments": "Knit Garments",
}
# Business line -> value-chain rows (each row is a flow of stage slugs).
LINE_FLOWS = {
	"Denim": [("Denim", ["recycling", "fiber-dyeing", "spinning", "indigo", "weaving-finishing", "garments"])],
	"Home Textile": [
		("Home Textile — Towels", ["spinning", "terry-weaving", "processing", "cut-to-piece", "packing"]),
		("Home Textile — Bed Linen", ["flat-weaving", "printing", "cut-to-piece"]),
	],
	"Knitting": [("Knitting", ["spinning", "knitting", "knit-dyeing", "knit-finishing", "knit-garments"])],
}
BUSINESS_LINES = ("Denim", "Home Textile", "Knitting", "All")
DEFAULT_LINE = "Denim"
LINE_DASHBOARDS = ("command-center", "production", "finance")


def line_flows(line: str | None) -> list[tuple[str, list[str]]]:
	if line == "All":
		return [flow for flows in LINE_FLOWS.values() for flow in flows]
	return LINE_FLOWS.get(line or DEFAULT_LINE) or LINE_FLOWS[DEFAULT_LINE]


def line_stages(line: str | None) -> tuple[str, ...]:
	slugs = dict.fromkeys(s for _title, row in line_flows(line) for s in row)
	return tuple(dict.fromkeys(stage for slug in slugs for stage in SLUG_STAGES[slug]))


def line_slugs(line: str | None) -> list[str]:
	return list(dict.fromkeys(s for _title, row in line_flows(line) for s in row))


def fiscal_year_start(date) -> object:
	fy = frappe.db.get_value(
		"Fiscal Year", {"year_start_date": ["<=", date], "year_end_date": [">=", date], "disabled": 0}, "year_start_date"
	)
	return getdate(fy) if fy else getdate(f"{getdate(date).year}-01-01")


def period_range(period: str, from_date=None, to_date=None) -> tuple:
	end = getdate(today())
	if period == "Today":
		return end, end
	if period == "This Week":
		return add_days(end, -end.weekday()), end
	if period == "MTD":
		return get_first_day(end), end
	if period == "QTD":
		return get_quarter_start(end), end
	if period == "YTD":
		return fiscal_year_start(end), end
	if period == "Last 90 days":
		return add_days(end, -89), end
	if period == "Custom":
		if not (from_date and to_date):
			frappe.throw(_("Custom period needs From and To dates."))
		return getdate(from_date), getdate(to_date)
	return add_days(end, -29), end


def compare_range(basis: str, start, end) -> tuple | None:
	if basis == "Same period last year":
		return add_years(start, -1), add_years(end, -1)
	if basis == "Previous period":
		days = date_diff(end, start) + 1
		return add_days(start, -days), add_days(start, -1)
	return None


def parse(filters) -> frappe._dict:
	if isinstance(filters, str):
		filters = json.loads(filters or "{}")
	f = frappe._dict(filters or {})
	period = f.get("period") if f.get("period") in PERIODS else DEFAULT_PERIOD
	start, end = period_range(period, f.get("from_date"), f.get("to_date"))
	basis = f.get("compare_to") if f.get("compare_to") in COMPARE_TO else DEFAULT_COMPARE
	compare = compare_range(basis, start, end)
	stage = f.get("stage") or None
	slug = f.get("stage_slug") or None
	return frappe._dict(
		company=f.get("company") or frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company"),
		period=period,
		from_date=getdate(start),
		to_date=getdate(end),
		compare_to=basis,
		compare_from=compare[0] if compare else None,
		compare_until=compare[1] if compare else None,
		plant=f.get("plant") or None,
		stage=stage,
		stage_slug=slug,
		stages=SLUG_STAGES.get(slug) or ((stage,) if stage else None),
		business_line=f.get("business_line") if f.get("business_line") in BUSINESS_LINES else DEFAULT_LINE,
		customer=f.get("customer") or None,
		item_group=f.get("item_group") or None,
		refresh=bool(f.get("refresh")),
	)


def shifted(ctx: frappe._dict, start, end) -> frappe._dict:
	"""Same filters over another window (used for comparisons)."""
	return frappe._dict(ctx, from_date=getdate(start), to_date=getdate(end))


def month_starts(end, months: int = 12) -> list:
	first = get_first_day(end)
	return [add_months(first, -i) for i in range(months - 1, -1, -1)]
