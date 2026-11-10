"""Payload builders shared by every dashboard (Part C §4.2)."""

from collections import defaultdict

import frappe
from frappe.utils import add_days, add_months, flt, get_first_day, getdate

from textile_mill.dashboards import kpi as K
from textile_mill.dashboards import targets
from textile_mill.dashboards.filters import shifted

SPARK_POINTS = 14
LEVEL_KPIS = {"INVENTORY_VALUE", "WIP_VALUE", "CASH_POSITION", "ORDER_BOOK"}
SUM_KPIS = {"REVENUE", "PRODUCTION_VALUE", "BOOKED", "DELIVERED", "PURCHASES", "DOWNTIME_HRS"}


def unit_format(unit: str | None) -> str:
	if unit == "%":
		return "percent"
	if unit and unit.startswith("PKR"):
		return "currency"
	if unit in ("count", "pcs"):
		return "int"
	return "float"


def route(*parts, **filters) -> dict:
	return {"route": [p for p in parts if p], "filters": {k: v for k, v in filters.items() if v not in (None, "")}}


def report_route(report: str, ctx, **extra) -> dict:
	return route("query-report", report, company=ctx.company, from_date=str(ctx.from_date), to_date=str(ctx.to_date), **extra)


def mark_synthetic(ctx) -> None:
	ctx.synthetic = True


def snapshot_series(ctx, code: str, stage: str | None, start, end) -> list[tuple]:
	rows = frappe.db.sql(
		"""select snapshot_date, value, is_synthetic from `tabKPI Daily Snapshot`
		where kpi = %(kpi)s and ifnull(stage, '') = %(stage)s and ifnull(plant, '') = %(plant)s
		and snapshot_date between %(start)s and %(end)s order by snapshot_date""",
		{"kpi": code, "stage": stage or "", "plant": ctx.get("plant") or "", "start": start, "end": end},
		as_dict=True,
	)
	if any(r.is_synthetic for r in rows):
		mark_synthetic(ctx)
	return [(r.snapshot_date, flt(r.value)) for r in rows]


def snapshot_aggregate(ctx, code: str, stage: str | None, start, end) -> float | None:
	"""A KPI over a past window from daily snapshots, used when live transactions don't reach that far back."""
	points = snapshot_series(ctx, code, stage, start, end)
	if not points:
		return None
	if code in SUM_KPIS:
		return sum(v for _d, v in points)
	if code in LEVEL_KPIS:
		return points[-1][1]
	return sum(v for _d, v in points) / len(points)


def sparkline(ctx, code: str, stage: str | None = None) -> list[float]:
	end = getdate(ctx.to_date)
	series = dict(snapshot_series(ctx, code, stage, add_days(end, -(SPARK_POINTS - 1)), end))
	points = [series.get(add_days(end, -i)) for i in range(SPARK_POINTS - 1, -1, -1)]
	return [p for p in points if p is not None]


def monthly_trend(ctx, code: str, stage: str | None = None, months: int = 12) -> tuple[list[str], list]:
	end = getdate(ctx.to_date)
	start = add_months(get_first_day(end), -(months - 1))
	buckets = defaultdict(list)
	for d, v in snapshot_series(ctx, code, stage, start, end):
		buckets[get_first_day(d)].append((d, v))
	labels, values = [], []
	for i in range(months):
		month = add_months(start, i)
		labels.append(month.strftime("%b %y"))
		points = buckets.get(month, [])
		if not points:
			values.append(None)
		elif code in LEVEL_KPIS:
			values.append(round(points[-1][1], 2))
		elif code in SUM_KPIS:
			values.append(round(sum(v for _d, v in points), 2))
		else:
			values.append(round(sum(v for _d, v in points) / len(points), 2))
	return labels, values


def daily_trend(ctx, code: str, stage: str | None = None, days: int = 30) -> tuple[list[str], list]:
	end = getdate(ctx.to_date)
	series = dict(snapshot_series(ctx, code, stage, add_days(end, -(days - 1)), end))
	labels, values = [], []
	for i in range(days - 1, -1, -1):
		d = add_days(end, -i)
		labels.append(d.strftime("%d %b"))
		values.append(round(series[d], 2) if d in series else None)
	return labels, values


def tile(ctx, code: str, stage: str | None = None, label: str | None = None, unit: str | None = None,
		drilldown: dict | None = None, value: dict | None = None, tile_id: str | None = None, compare: bool = True,
		show_standard: dict | None = None) -> dict:
	definition = frappe.get_cached_doc("KPI Definition", code) if frappe.db.exists("KPI Definition", code) else None
	res = value or K.calculate(code, ctx, stage)
	unit = unit or (definition.unit if definition else None)
	payload = {
		"id": tile_id or (code.lower() + (f"_{frappe.scrub(stage)}" if stage else "")),
		"label": label or (definition.kpi_name if definition else code),
		"value": res["value"],
		"format": unit_format(unit),
		"unit": "" if unit in ("%", "PKR", "count") else unit,
		"tooltip": definition.description if definition else None,
		"direction": definition.direction if definition else "Higher is better",
		"target": targets.evaluate(code, res["value"], stage, ctx.get("plant"), ctx.to_date),
		"spark": sparkline(ctx, code, stage),
		"drilldown": drilldown,
	}
	if show_standard:
		payload["standard"] = show_standard
	if compare and ctx.get("compare_from") and res["value"] is not None:
		prev = K.calculate(code, shifted(ctx, ctx.compare_from, ctx.compare_until), stage)["value"]
		if prev in (None, 0):
			prev = snapshot_aggregate(ctx, code, stage, ctx.compare_from, ctx.compare_until)
		if prev not in (None, 0):
			payload["compare"] = {"value": prev, "delta_pct": (flt(res["value"]) - flt(prev)) / abs(flt(prev)) * 100, "basis": ctx.compare_to}
	elif ctx.get("compare_to") == "Target" and payload["target"]:
		t = payload["target"]["value"]
		if t and res["value"] is not None:
			payload["compare"] = {"value": t, "delta_pct": (flt(res["value"]) - t) / abs(t) * 100, "basis": "Target"}
	return payload


SLOW_WIDGET_SECONDS = 2.0


def run_widgets(builders: list) -> list[dict]:
	"""Build each widget independently: one failure or slow query must not blank the dashboard.
	A builder may return one widget or a list of widgets."""
	import time

	out = []
	for build in builders:
		started = time.monotonic()
		try:
			built = build()
			out.extend(built if isinstance(built, list) else [built])
		except Exception:
			frappe.log_error(title="Textile Mill dashboard widget failed")
			out.append(widget(f"error_{len(out)}", "error", "Widget unavailable", 6, {}, note="This widget failed to load; the error was logged."))
		elapsed = time.monotonic() - started
		if elapsed > SLOW_WIDGET_SECONDS:
			frappe.logger("textile_mill.dashboards").warning(f"slow widget {out[-1].get('id')}: {elapsed:.2f}s")
	return out


def widget(widget_id: str, wtype: str, title: str, span: int, data: dict, drilldown: dict | None = None,
		note: str | None = None, explain: str | None = None, synthetic: bool = False) -> dict:
	return {"id": widget_id, "type": wtype, "title": title, "span": span, "data": data, "drilldown": drilldown,
		"note": note, "explain": explain, "synthetic": synthetic}


def table(columns: list[tuple], rows: list[dict]) -> dict:
	"""columns: (label, field, format)."""
	return {"columns": [{"label": c[0], "field": c[1], "format": c[2] if len(c) > 2 else "data"} for c in columns], "rows": rows}


def series(name: str, values: list, kind: str | None = None, axis: int = 0, stack: str | None = None) -> dict:
	out = {"name": name, "values": values}
	if kind:
		out["type"] = kind
	if axis:
		out["axis"] = axis
	if stack:
		out["stack"] = stack
	return out


def trend_widget(ctx, widget_id: str, title: str, span: int, lines: list[tuple], months: int = 12, unit: str = "",
		drilldown: dict | None = None, kind: str = "line") -> dict:
	"""lines: (label, kpi_code, stage)."""
	before = bool(ctx.get("synthetic"))
	ctx.synthetic = False
	labels, out = [], []
	for i, (label, code, stage) in enumerate(lines):
		labels, values = monthly_trend(ctx, code, stage, months)
		if kind == "combo":
			out.append(series(label, values, "bar" if i == 0 else "line", axis=0 if i == 0 else 1))
		else:
			out.append(series(label, values))
	synthetic = bool(ctx.get("synthetic"))
	ctx.synthetic = before or synthetic
	return widget(widget_id, kind, title, span, {"categories": labels, "series": out, "unit": unit}, drilldown, synthetic=synthetic)
