"""D7 Stage drill-down: one page per value-chain stage, selected by slug (Part C §7 D7)."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import date_diff, flt

from textile_mill import reports_lib as rl
from textile_mill import reports_lib_ht as ht
from textile_mill import reports_lib_knit as kn
from textile_mill.dashboards import kpi as K
from textile_mill.dashboards import queries as Q
from textile_mill.dashboards import targets
from textile_mill.dashboards.common import run_widgets, monthly_trend, report_route, route, table, tile, widget
from textile_mill.dashboards.filters import SLUG_STAGES, SLUG_TITLES


def build(ctx) -> tuple[list, list]:
	slug = ctx.get("stage_slug")
	if slug not in SLUG_STAGES:
		frappe.throw(_("Unknown stage {0}").format(slug))
	stages = SLUG_STAGES[slug]
	summary = {r.stage: r for r in rl.stage_yield_summary(Q.rf(ctx))}
	main = next((s for s in reversed(stages) if s in summary), stages[-1])
	costs = {r.stage: r for r in rl.cost_per_unit_by_stage(Q.rf(ctx))}
	y = summary.get(main)
	cost = costs.get(main)
	buffer = Q.stage_buffer(ctx, stages[0])
	capacity = Q.stage_capacity_per_day(stages[0])
	garments = main in ("Garments", "Knit Garments")
	per = 1 if main == "Knit Garments" else 100
	yield_value = K.result(y.output_per_input * per if garments else y.yield_pct) if y else K.result(None)
	tiles = [
		tile(ctx, "STAGE_OUTPUT", main, label=f"Output ({y.output_uom})" if y else "Output", unit=y.output_uom if y else None,
			value=K.result(y.output_qty if y else None), tile_id="output", compare=False),
		tile(ctx, "STAGE_YIELD", main, label=("Pieces per kg" if per == 1 else "Pieces per 100 m") if garments else "Yield %", value=yield_value, unit="pcs" if garments else "%",
			drilldown=report_route("Stage Yield Report", ctx, dm_stage=main), compare=not garments),
		tile(ctx, "COST_PER_UNIT", main, label=f"Cost / {y.output_uom}" if y else "Cost / unit",
			drilldown=report_route("Production Cost per Unit", ctx, dm_stage=main),
			show_standard={"value": cost.standard_per_unit, "label": "Std"} if cost else None),
		tile(ctx, "OEE", label="OEE %", value=K.result(K.oee_parts(ctx, stages)["oee"]), compare=False),
		tile(ctx, "WASTE_PCT", stages[0], label="Waste %", drilldown=report_route("Stage Yield Report", ctx, dm_stage=stages[0])),
		dict(tile(ctx, "WIP_WAITING", label=f"WIP Waiting ({buffer['uom']})" if buffer["uom"] else "WIP Waiting", value=K.result(buffer["qty"]), unit=buffer["uom"],
			tile_id="wip_waiting", compare=False),
			subtitle=f"{buffer['qty'] / capacity:.1f} days of capacity" if capacity else None),
	]
	widgets = [
		lambda: input_output(ctx, stages),
		lambda: cost_trend(ctx, main, cost),
		lambda: machine_table(ctx, stages),
		lambda: downtime(ctx, stages),
		lambda: qi_results(ctx, stages),
		lambda: SPECIFIC.get(slug, lambda _ctx: [])(ctx),
	]
	return tiles, run_widgets(widgets)


def title(ctx) -> str:
	return SLUG_TITLES.get(ctx.get("stage_slug"), "Stage")


def input_output(ctx, stages) -> dict:
	labels, ins, outs, ylds = Q.daily_flow(ctx, stages)
	return widget("input_output", "combo", "Daily Input vs Output (last 30 days)", 8,
		{"categories": labels, "series": [{"name": "Input", "values": ins, "type": "bar"}, {"name": "Output", "values": outs, "type": "bar"},
			{"name": "Yield %", "values": ylds, "type": "line", "axis": 1}], "unit": ""})


def cost_trend(ctx, stage, cost) -> dict:
	labels, values = monthly_trend(ctx, "COST_PER_UNIT", stage, months=6)
	std = round(cost.standard_per_unit, 2) if cost else None
	return widget("cost_trend", "line", f"{stage} Cost per Unit vs Standard (6 months)", 4,
		{"categories": labels, "series": [{"name": "Actual", "values": values}, {"name": "Standard", "values": [std] * len(labels), "dashed": True}],
			"format": "currency"}, synthetic=bool(ctx.get("synthetic")))


def machine_table(ctx, stages) -> dict:
	run = K.run_minutes(ctx, stages)
	down = K.downtime_minutes(ctx, stages)
	days = date_diff(ctx.to_date, ctx.from_date) + 1
	rows = []
	for w in K.stage_workstations(stages):
		r, d = run.get(w.name, 0), down.get(w.name, 0)
		if not (r or d):
			continue
		planned = flt(w.dm_planned_hours_per_day or 8) * 60 * days
		rows.append({"workstation": w.name, "type": w.workstation_type, "run_h": r / 60, "down_h": d / 60,
			"utilisation": r / planned * 100 if planned else None, "availability": r / (r + d) * 100 if (r + d) else None,
			"_status": {"availability": "red" if (r + d) and r / (r + d) < 0.85 else None},
			"_route": {"workstation": ["Form", "Workstation", w.name]}})
	rows.sort(key=lambda x: x["availability"] or 0)
	return widget("machines", "table", "Machines", 6, table(
		[("Workstation", "workstation", "link"), ("Type", "type"), ("Run (h)", "run_h", "float"), ("Downtime (h)", "down_h", "float"),
			("Utilisation %", "utilisation", "percent"), ("Availability %", "availability", "percent")], rows),
		note=None if rows else "No job cards or shift logs in the period.")


def downtime(ctx, stages) -> dict:
	return widget("downtime", "pareto", "Downtime Reasons", 6, Q.pareto(Q.downtime_by_reason(ctx, stages)),
		drilldown=route("List", "Machine Downtime Log", stage=["in", list(stages)]))


def qi_results(ctx, stages) -> dict:
	rows = Q.recent_qi(ctx, stages)
	for r in rows:
		r._status = {"status": "red" if r.status == "Rejected" else "green"}
		r._route = {"name": ["Form", "Quality Inspection", r.name]}
	return widget("qi_results", "table", "Latest Quality Inspections", 12, table(
		[("QI", "name", "link"), ("Date", "report_date", "date"), ("Item", "item_code"), ("Batch", "batch_no"), ("Status", "status"),
			("Out-of-range", "failed")], rows), note=None if rows else "No inspections in the period.")


# ---------------------------------------------------------------- stage-specific panels
def _recycling(ctx) -> list:
	from textile_mill.dashboards.widgets.procurement import _recovery_by_supplier

	data = _recovery_by_supplier(ctx)
	target = targets.get_target("STAGE_YIELD", "Cotton Recycling")
	return [widget("recovery_by_supplier", "bar", "Recovery Yield by Waste Supplier", 12,
		{"categories": list(data), "series": [{"name": "Recovery %", "values": [round(v, 1) for v in data.values()]}], "unit": "%",
			"mark_line": flt(target.target_value) if target else None})]


def _dye_shade(ctx, stage: str) -> list:
	rows = frappe.db.sql("""select qi.batch_no, qi.report_date, r.reading_1 de, qi.status from `tabQuality Inspection Reading` r
		join `tabQuality Inspection` qi on qi.name = r.parent join `tabItem` i on i.name = qi.item_code
		where qi.docstatus = 1 and r.specification like 'Delta E%%' and i.dm_stage = %(stage)s
		and qi.report_date between %(from_date)s and %(to_date)s order by qi.report_date, qi.creation""", {**ctx, "stage": stage}, as_dict=True)
	shade = widget("shade_by_batch", "bar", f"{stage}: Delta E by Batch (tolerance 1.0)", 6,
		{"categories": [r.batch_no or r.report_date.strftime("%d %b") for r in rows], "series": [{"name": "Delta E",
			"values": [round(flt(r.de), 2) for r in rows]}], "mark_line": 1.0, "threshold_high": 1.0, "unit": "ΔE"},
		note=None if rows else "No Delta E readings in the period.")
	variance = [r for r in rl.recipe_variance(Q.rf(ctx)) if not r.get("is_total") and r.get("stage") == stage]
	chem = widget("recipe_variance", "table", "Recipe Consumption Variance", 6, table(
		[("Work Order", "work_order"), ("Chemical", "item_code"), ("Standard", "standard_qty", "float"), ("Actual", "actual_qty", "float"),
			("Variance %", "variance_pct", "percent")], variance[:20]), drilldown=report_route("Recipe Consumption Variance", ctx))
	return [shade, chem]


def _spinning(ctx) -> list:
	rows = frappe.db.sql("""select r.specification, avg(r.reading_1) avg_value, min(r.reading_1) min_value, max(r.reading_1) max_value,
		count(*) n, sum(r.status = 'Rejected') failed from `tabQuality Inspection Reading` r join `tabQuality Inspection` qi on qi.name = r.parent
		join `tabItem` i on i.name = qi.item_code where qi.docstatus = 1 and i.dm_stage = 'Spinning'
		and qi.report_date between %(from_date)s and %(to_date)s group by r.specification""", ctx, as_dict=True)
	return [widget("yarn_quality", "table", "Yarn Quality Parameters", 12, table(
		[("Parameter", "specification"), ("Average", "avg_value", "float"), ("Min", "min_value", "float"), ("Max", "max_value", "float"),
			("Tests", "n", "int"), ("Failed", "failed", "int")], rows), note=None if rows else "No yarn inspections in the period.")]


def _indigo(ctx) -> list:
	out = _dye_shade(ctx, "Indigo Dyeing")
	rows = frappe.get_all("Indigo Range Log", filters={"docstatus": 1, "posting_date": ["between", [ctx.from_date, ctx.to_date]]},
		fields=["name", "posting_date", "range_speed_m_min", "avg_ph", "avg_indigo_g_l", "avg_hydro_g_l", "avg_redox_mv", "status"],
		order_by="posting_date")
	for r in rows:
		r._status = {"status": "red" if r.status == "Out of Spec" else "green"}
		r._route = {"name": ["Form", "Indigo Range Log", r.name]}
	out.append(widget("range_log", "table", "Indigo Range Logs", 12, table(
		[("Log", "name", "link"), ("Date", "posting_date", "date"), ("Speed m/min", "range_speed_m_min", "float"), ("pH", "avg_ph", "float"),
			("Indigo g/l", "avg_indigo_g_l", "float"), ("Hydro g/l", "avg_hydro_g_l", "float"), ("Redox mV", "avg_redox_mv", "float"),
			("Status", "status")], rows)))
	return out


def _loom_by_shift(ctx, loom_type: str, width: int = 6) -> dict:
	by_shift = defaultdict(lambda: [0.0, 0.0])
	for r in rl.loom_efficiency(Q.rf(ctx, loom_type=loom_type)):
		output = flt(r.meters) or flt(r.kg)
		by_shift[r.shift][0] += flt(r.efficiency_pct) * output
		by_shift[r.shift][1] += output
	shifts = sorted(by_shift)
	return widget("loom_by_shift", "bar", f"{loom_type} Loom Efficiency by Shift", width, {"categories": shifts,
		"series": [{"name": "Efficiency %", "values": [round(by_shift[s][0] / by_shift[s][1], 1) if by_shift[s][1] else None
			for s in shifts]}], "unit": "%", "mark_line": 85},
		drilldown=report_route("Loom Efficiency", ctx, loom_type=loom_type), note=None if shifts else "No loom shifts in the period.")


def _weaving_finishing(ctx) -> list:
	g = rl.grade_split(Q.rf(ctx))
	return [
		_loom_by_shift(ctx, "Air-jet Denim"),
		widget("grades", "donut", "Fabric Grades (m)", 6, {"items": [{"name": "A", "value": round(g["A"], 1), "color": "green"},
			{"name": "B", "value": round(g["B"], 1), "color": "amber"}, {"name": "Rejected", "value": round(g["Rejected"], 1), "color": "red"}],
			"unit": "m"}, drilldown=report_route("Fabric Grade Analysis", ctx)),
	]


def _garments(ctx, stage: str = "Garments") -> list:
	rows = frappe.db.sql(
		"""select c.name, c.posting_date, c.total_pieces, c.standard_fabric_m, c.fabric_issued_m, c.cutting_variance_m,
			c.cutting_variance_pct as variance_pct from `tabCut Plan` c join `tabItem` i on i.name = c.style_template
		where c.docstatus = 1 and c.company = %(company)s and c.posting_date between %(from_date)s and %(to_date)s
		and i.dm_stage = %(stage)s order by c.posting_date""",
		{**ctx, "stage": stage},
		as_dict=True,
	)
	for r in rows:
		r._status = {"variance_pct": "red" if flt(r.variance_pct) > 5 else ("amber" if flt(r.variance_pct) > 3 else "green")}
		r._route = {"name": ["Form", "Cut Plan", r.name]}
	unit = "kg" if stage == "Knit Garments" else "m"
	return [widget("cut_plans", "table", "Cut Plans — fabric consumption vs marker", 12, table(
		[("Cut Plan", "name", "link"), ("Date", "posting_date", "date"), ("Pieces", "total_pieces", "int"),
			(f"Standard {unit}", "standard_fabric_m", "float"), (f"Actual {unit}", "fabric_issued_m", "float"),
			(f"Variance {unit}", "cutting_variance_m", "float"), ("Variance %", "variance_pct", "percent")], rows),
		note=None if rows else "No cut plans in the period.")]


def _recipe_variance(ctx, stage: str) -> dict:
	variance = [r for r in rl.recipe_variance(Q.rf(ctx)) if not r.get("is_total") and r.get("stage") == stage]
	return widget("recipe_variance", "table", f"{stage}: Recipe Consumption Variance", 12, table(
		[("Work Order", "work_order"), ("Chemical", "item_code"), ("Standard", "standard_qty", "float"), ("Actual", "actual_qty", "float"),
			("Variance %", "variance_pct", "percent")], variance[:20]), drilldown=report_route("Recipe Consumption Variance", ctx),
		note=None if variance else "No recipe work orders in the period.")


def _cut_to_piece(ctx) -> list:
	rows = ht.ctp_entries(Q.rf(ctx))
	for r in rows:
		r._status = {"ctp_yield_pct": "green" if flt(r.ctp_yield_pct) >= 97 else ("amber" if flt(r.ctp_yield_pct) >= 96 else "red")}
		r._route = {"ctp_production_entry": ["Form", "CTP Production Entry", r.ctp_production_entry]}
	checks = ht.weight_checks(Q.rf(ctx))
	return [
		widget("ctp_entries", "table", "Cut-to-Piece Yield & Grading", 7, table(
			[("Entry", "ctp_production_entry", "link"), ("Product", "product_item"), ("Planned", "pieces_planned", "int"),
				("A", "pieces_a", "int"), ("Seconds", "pieces_seconds", "int"), ("Yield %", "ctp_yield_pct", "percent"),
				("Seconds %", "seconds_pct", "percent")], rows), drilldown=report_route("CTP Yield and Grading", ctx),
			note=None if rows else "No CTP entries in the period."),
		_weight_compliance(checks, 5, ctx),
	]


def _weight_compliance(checks, width: int, ctx) -> dict:
	return widget("weight_compliance", "bar", "Piece Weight vs Target (kg)", width, {
		"categories": [r.item_code for r in checks],
		"series": [{"name": "Target", "values": [r.target_weight_kg for r in checks], "dashed": True},
			{"name": "Average", "values": [round(flt(r.avg_weight_kg), 4) for r in checks]}], "unit": "kg"},
		drilldown=report_route("Weight Compliance", ctx), note=None if checks else "No weight checks in the period.")


def _packing(ctx) -> list:
	sets = ht.set_completion({"company": ctx.company})
	for r in sets:
		r._status = {"completion_pct": "green" if r.completion_pct >= 100 else ("amber" if r.completion_pct >= 95 else "red")}
	ships = ht.shipments(Q.rf(ctx))
	return [
		widget("set_completion", "table", "Set Completion", 6, table(
			[("Set", "item_code"), ("On hand", "on_hand", "float"), ("Buildable", "buildable", "int"), ("Open SO", "open_so_qty", "float"),
				("Limiting", "limiting_component"), ("Completion %", "completion_pct", "percent")], sets),
			drilldown=report_route("Set Completion", ctx)),
		widget("shipments", "table", "Cartons & Shipments", 6, table(
			[("Sales Order", "sales_order"), ("Customer", "customer"), ("Cartons", "cartons", "int"), ("Shipped", "cartons_shipped", "int"),
				("Gross kg", "gross_kg", "float"), ("CBM", "cbm", "float")], ships),
			drilldown=report_route("Carton and Shipment Summary", ctx), note=None if ships else "No packing lists in the period."),
	]


def _knitting(ctx) -> list:
	rows = kn.knitting_rows(Q.rf(ctx))
	by_shift = defaultdict(lambda: [0.0, 0.0])
	machines = defaultdict(lambda: frappe._dict(kg=0.0, rolls=0, defects=0, stop=0.0, eff_kg=0.0))
	for r in rows:
		by_shift[r.shift][0] += flt(r.efficiency_pct) * flt(r.kg)
		by_shift[r.shift][1] += flt(r.kg)
		m = machines[r.machine]
		m.kg += flt(r.kg)
		m.rolls += flt(r.rolls_produced)
		m.defects += flt(r.defects_count)
		m.stop += flt(r.stop_minutes)
		m.eff_kg += flt(r.efficiency_pct) * flt(r.kg)
	shifts = sorted(by_shift)
	table_rows = [frappe._dict(machine=k, kg=v.kg, rolls=v.rolls, defects_per_roll=v.defects / v.rolls if v.rolls else 0,
		efficiency_pct=v.eff_kg / v.kg if v.kg else 0, stop_min=v.stop) for k, v in sorted(machines.items())]
	for r in table_rows:
		r._status = {"defects_per_roll": "red" if r.defects_per_roll > 1 else ("amber" if r.defects_per_roll > 0.5 else "green")}
	return [
		widget("knit_by_shift", "bar", "Knitting Efficiency by Shift", 5, {"categories": shifts, "series": [{"name": "Efficiency %",
			"values": [round(by_shift[s][0] / by_shift[s][1], 1) if by_shift[s][1] else None for s in shifts]}], "unit": "%",
			"mark_line": 85}, note=None if shifts else "No knitting shifts in the period."),
		widget("knit_machines", "table", "Circular Knitting Machines", 7, table(
			[("Machine", "machine"), ("Kg", "kg", "float"), ("Rolls", "rolls", "int"), ("Defects / roll", "defects_per_roll", "float"),
				("Efficiency %", "efficiency_pct", "percent"), ("Stop min", "stop_min", "float")], table_rows),
			drilldown=route("List", "Knitting Shift Production"), note=None if rows else "No knitting shifts in the period."),
	]


def _knit_dyeing(ctx) -> list:
	rows = kn.dye_batches(Q.rf(ctx))
	for r in rows:
		r._status = {"machine_load_pct": "green" if flt(r.machine_load_pct) >= 90 else ("amber" if flt(r.machine_load_pct) >= 80 else "red")}
		r._route = {"work_order": ["Form", "Work Order", r.work_order]}
	return [
		widget("dye_batches", "table", "Jet Batches — Machine Load", 6, table(
			[("Work Order", "work_order", "link"), ("Start", "start_date", "date"), ("Recipe", "dye_recipe"), ("Kg", "qty", "float"),
				("Load %", "machine_load_pct", "percent"), ("Status", "status")], rows),
			note=None if rows else "No knit dyeing batches in the period."),
		dict(_recipe_variance(ctx, "Knit Dyeing"), span=6),
	]


def _knit_finishing(ctx) -> list:
	rows = kn.fabric_tests(Q.rf(ctx))
	for r in rows:
		r._status = {"status": "red" if r.status == "Rejected" else "green"}
		r._route = {"name": ["Form", "Quality Inspection", r.name]}
	return [widget("fabric_tests", "table", "Shrinkage & Spirality (finished knit)", 12, table(
		[("QI", "name", "link"), ("Date", "report_date", "date"), ("Batch", "batch_no"), ("Test", "specification"),
			("Value %", "value", "float"), ("Status", "status")], rows), note=None if rows else "No fabric tests in the period.")]


SPECIFIC = {
	"recycling": _recycling,
	"fiber-dyeing": lambda ctx: _dye_shade(ctx, "Fiber Dyeing"),
	"spinning": _spinning,
	"indigo": _indigo,
	"weaving-finishing": _weaving_finishing,
	"garments": _garments,
	"terry-weaving": lambda ctx: [_loom_by_shift(ctx, "Terry", 12)],
	"flat-weaving": lambda ctx: [_loom_by_shift(ctx, "Flat Wide", 12)],
	"processing": lambda ctx: [_recipe_variance(ctx, "Processing")],
	"printing": lambda ctx: [_recipe_variance(ctx, "Printing")],
	"cut-to-piece": _cut_to_piece,
	"packing": _packing,
	"knitting": _knitting,
	"knit-dyeing": _knit_dyeing,
	"knit-finishing": _knit_finishing,
	"knit-garments": lambda ctx: _garments(ctx, "Knit Garments"),
}
