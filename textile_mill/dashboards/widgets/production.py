"""D2 Production & Efficiency (Production Director)."""

from collections import defaultdict

import frappe
from frappe.utils import add_days, date_diff, flt, getdate, now_datetime

from textile_mill import reports_lib as rl
from textile_mill.constants import PRODUCTION_STAGES
from textile_mill.dashboards import kpi as K
from textile_mill.dashboards import queries as Q
from textile_mill.dashboards.common import run_widgets, report_route, route, table, tile, widget
from textile_mill.dashboards.filters import SLUG_STAGES, SLUG_TITLES, line_slugs, line_stages


def build(ctx) -> tuple[list, list]:
	stages = ctx.get("stages") or line_stages(ctx.get("business_line"))
	ctx = frappe._dict(ctx, stages=stages)
	parts = K.oee_parts(ctx, stages)
	open_wo = K.open_work_orders(ctx)
	tiles = [
		tile(ctx, "PLAN_ATTAINMENT", label="Plan Attainment %", drilldown=route("List", "Work Order")),
		tile(ctx, "OEE", label=f"OEE % ({ctx.get('business_line') or 'Denim'})", value=K.result(parts["oee"]), drilldown=route("query-report", "Loom Efficiency")),
		tile(ctx, "AVAILABILITY", label="Availability %", value=K.result(parts["availability"]), compare=False),
		tile(ctx, "PERFORMANCE", label="Performance %", value=K.result(parts["performance"]), compare=False),
		tile(ctx, "QUALITY_RATE", label="Quality Rate %", value=K.result(parts["quality"]), compare=False),
		tile(ctx, "DOWNTIME_HRS", label="Unplanned Downtime (h)", drilldown=route("List", "Machine Downtime Log")),
		tile(ctx, "REDYE_PCT", label="Re-dye / Re-process %", drilldown=report_route("Corrective Report", ctx)),
		dict(tile(ctx, "OPEN_WO", label="Open Work Orders", value=open_wo, compare=False,
			drilldown=route("List", "Work Order", status=["in", ["Not Started", "In Process"]])),
			subtitle=f"{int(flt(open_wo['numerator']))} delayed"),
	]
	widgets = [
		lambda: oee_by_stage(ctx),
		lambda: plan_vs_actual(ctx),
		lambda: production_trend(ctx, stages),
		lambda: bottleneck(ctx),
		lambda: downtime_pareto(ctx, stages),
		lambda: downtime_vs_run(ctx, stages),
		lambda: machine_heatmap(ctx, stages),
		lambda: loom_ranking(ctx),
		lambda: wastage_by_stage(ctx),
		lambda: wip_aging(ctx),
		lambda: pending_work_orders(ctx),
	]
	return tiles, run_widgets(widgets)


def oee_by_stage(ctx) -> dict:
	gauges = []
	for slug in line_slugs(ctx.get("business_line")):
		value = K.oee_parts(ctx, SLUG_STAGES[slug])["oee"]
		gauges.append({"name": SLUG_TITLES[slug], "value": round(value, 1) if value is not None else None, "max": 100,
			"format": "percent", "route": f"/app/dm-stage/{slug}"})
	return widget("oee_by_stage", "gauge_group", "OEE by Stage", 12, {"gauges": gauges},
		explain="OEE = Availability × Performance × Quality. Run time comes from job cards and loom shifts; downtime from downtime logs and loom stops.")


def plan_vs_actual(ctx) -> dict:
	rows = frappe.db.sql(
		"""select dm_stage, sum(qty) planned, sum(produced_qty) produced from `tabWork Order` where docstatus = 1
		and company = %(company)s and status != 'Stopped' and date(planned_start_date) between %(from_date)s and %(to_date)s
		group by dm_stage""",
		ctx,
		as_dict=True,
	)
	by_stage = {r.dm_stage: r for r in rows}
	stages = [s for s in line_stages(ctx.get("business_line")) if s in by_stage]
	actual = [round(flt(by_stage[s].produced) / flt(by_stage[s].planned) * 100, 1) if flt(by_stage[s].planned) else None for s in stages]
	return widget("plan_vs_actual", "grouped_bar", "Plan vs Actual by Stage (% of plan)", 6,
		{"categories": stages, "series": [{"name": "Plan", "values": [100] * len(stages)}, {"name": "Actual", "values": actual}],
			"unit": "%", "mark_line": 100}, drilldown=route("List", "Work Order"))


def production_trend(ctx, stages) -> dict:
	end = getdate(ctx.to_date)
	start = add_days(end, -29)
	daily = defaultdict(lambda: defaultdict(float))
	for r in rl.manufacture_entries({"company": ctx.company, "from_date": start, "to_date": end}):
		if r.dm_stage in stages:
			daily[r.dm_stage][getdate(r.posting_date)] += flt(r.output_qty)
	labels = [add_days(start, i) for i in range(30)]
	out = []
	for stage in [s for s in stages if s in daily]:
		total = sum(daily[stage].values())
		days_active = len(daily[stage]) or 1
		avg = total / days_active
		out.append({"name": stage, "values": [round(daily[stage][d] / avg * 100, 0) if d in daily[stage] else None for d in labels]})
	return widget("production_trend", "line", "Daily Output by Stage (index, active-day average = 100)", 6,
		{"categories": [d.strftime("%d %b") for d in labels], "series": out, "unit": "", "mark_line": 100, "connect_nulls": False},
		note="Indexed so stages with different units (kg, m, pcs) share one axis.")


def bottleneck(ctx) -> dict:
	rows = []
	for slug, stages in SLUG_STAGES.items():
		buffer = Q.stage_buffer(ctx, stages[0])
		capacity = Q.stage_capacity_per_day(stages[0])
		queue_days = buffer["qty"] / capacity if capacity else None
		rows.append({"stage": SLUG_TITLES[slug], "wip": buffer["qty"], "uom": buffer["uom"], "capacity": capacity,
			"queue_days": queue_days, "_route": {"stage": f"/app/dm-stage/{slug}"}})
	worst = max((r["queue_days"] or 0) for r in rows) if rows else 0
	for r in rows:
		r["_status"] = {"queue_days": "red" if worst and r["queue_days"] == worst else None}
	return widget("bottleneck", "table", "Bottleneck Finder", 6, table(
		[("Stage", "stage", "link"), ("WIP Waiting", "wip", "float"), ("UOM", "uom"), ("Capacity / day", "capacity", "float"),
			("Queue (days)", "queue_days", "float")], rows),
		explain="Queue days = quantity waiting ÷ bottleneck capacity per day (weakest workstation type × planned hours). The longest queue is red.")


def downtime_pareto(ctx, stages) -> dict:
	items = Q.downtime_by_reason(ctx, stages)
	return widget("downtime_pareto", "pareto", "Downtime by Reason (Pareto)", 6, Q.pareto(items),
		drilldown=route("List", "Machine Downtime Log"))


def downtime_vs_run(ctx, stages) -> dict:
	run = K.run_minutes(ctx, stages)
	down = K.downtime_minutes(ctx, stages)
	types = {w.name: w.workstation_type or w.name for w in K.stage_workstations(stages)}
	run_t, down_t = defaultdict(float), defaultdict(float)
	for w, m in run.items():
		run_t[types.get(w, w)] += m / 60
	for w, m in down.items():
		down_t[types.get(w, w)] += m / 60
	categories = sorted(set(run_t) | set(down_t), key=lambda t: -(run_t[t] + down_t[t]))
	return widget("downtime_vs_run", "stacked_bar", "Run vs Downtime by Machine Type (hours)", 6,
		{"categories": categories, "series": [
			{"name": "Run", "values": [round(run_t[c], 1) for c in categories], "stack": "t"},
			{"name": "Downtime", "values": [round(down_t[c], 1) for c in categories], "stack": "t"}],
			"horizontal": True, "unit": "h"})


def machine_heatmap(ctx, stages) -> dict:
	return widget("machine_heatmap", "heatmap", "Machine Utilisation — last 14 days (%)", 12, Q.utilisation_heatmap(ctx, stages))


def loom_ranking(ctx) -> dict:
	by_loom = defaultdict(lambda: {"meters": 0, "eff_w": 0, "breaks": 0, "stops": 0, "shifts": 0})
	for r in K.loom_rows(ctx, ctx.get("stages") or line_stages(ctx.get("business_line"))):
		x = by_loom[r.loom]
		output = flt(r.meters) or flt(r.kg)
		x["meters"] += output
		x["eff_w"] += flt(r.efficiency_pct) * output
		x["breaks"] += flt(r.warp_breaks) + flt(r.weft_breaks)
		x["stops"] += flt(r.stop_minutes)
		x["shifts"] += 1
	rows = [{"loom": k, "efficiency": v["eff_w"] / v["meters"] if v["meters"] else 0, "meters": v["meters"],
		"breaks_per_shift": v["breaks"] / v["shifts"], "stop_min": v["stops"], "_route": {"loom": ["Form", "Workstation", k]}}
		for k, v in by_loom.items()]
	rows.sort(key=lambda r: r["efficiency"])
	for r in rows:
		r["_status"] = {"efficiency": "red" if r["efficiency"] < 80 else ("amber" if r["efficiency"] < 85 else None)}
	return widget("loom_ranking", "table", "Loom Ranking — bottom 10 by efficiency", 6, table(
		[("Loom", "loom", "link"), ("Efficiency %", "efficiency", "percent"), ("Meters", "meters", "float"),
			("Breaks / shift", "breaks_per_shift", "float"), ("Stop min", "stop_min", "float")], rows[:10]),
		drilldown=report_route("Loom Efficiency", ctx))


def wastage_by_stage(ctx) -> dict:
	rows = {r.stage: r for r in rl.stage_yield_summary(Q.rf(ctx))}
	stages = [s for s in line_stages(ctx.get("business_line")) if s in rows and rows[s].same_uom]
	waste = [round(flt(rows[s].waste_pct), 2) for s in stages]
	loss = [round(max(100 - flt(rows[s].yield_pct) - flt(rows[s].waste_pct), 0), 2) for s in stages]
	return widget("wastage_by_stage", "stacked_bar", "Wastage by Stage (% of input)", 6,
		{"categories": stages, "series": [{"name": "Saleable waste", "values": waste, "stack": "w"},
			{"name": "Invisible loss", "values": loss, "stack": "w"}], "unit": "%"},
		drilldown=report_route("Stage Yield Report", ctx))


def wip_aging(ctx) -> dict:
	rows = Q.stock_by_age(ctx, ("WIP",))
	buckets = [b[1] for b in Q.AGE_BUCKETS]
	stages = sorted({r.stage or "Other" for r in rows}, key=lambda s: PRODUCTION_STAGES.index(s) if s in PRODUCTION_STAGES else 99)
	data = defaultdict(float)
	for r in rows:
		data[(r.stage or "Other", r.bucket)] += flt(r.value)
	return widget("wip_aging", "stacked_bar", "WIP Aging by Stage (value)", 6,
		{"categories": stages, "series": [{"name": b, "values": [round(data[(s, b)], 0) for s in stages], "stack": "a"} for b in buckets],
			"format": "currency"}, note=None if rows else "No batch-tracked WIP on hand.")


def pending_work_orders(ctx) -> dict:
	rows = frappe.db.sql(
		"""select name, production_item, dm_stage, qty, produced_qty, status, planned_end_date from `tabWork Order`
		where docstatus = 1 and company = %(company)s and status in ('Not Started', 'In Process')
		order by planned_end_date limit 50""",
		ctx,
		as_dict=True,
	)
	now = now_datetime()
	for r in rows:
		r.days_late = max(date_diff(now, r.planned_end_date), 0) if r.planned_end_date else 0
		r.pending = flt(r.qty) - flt(r.produced_qty)
		r._status = {"days_late": "red" if r.days_late > 2 else ("amber" if r.days_late else None)}
		r._route = {"name": ["Form", "Work Order", r.name]}
	rows.sort(key=lambda r: -r.days_late)
	return widget("pending_wo", "table", "Pending Work Orders", 12, table(
		[("Work Order", "name", "link"), ("Item", "production_item"), ("Stage", "dm_stage"), ("Pending", "pending", "float"),
			("Status", "status"), ("Planned End", "planned_end_date", "date"), ("Days Late", "days_late", "int")], rows),
		note=None if rows else "No open work orders.")
