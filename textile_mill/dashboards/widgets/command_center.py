"""D1 Command Center (CEO): the whole business on one screen."""

import frappe
from frappe.utils import add_days, flt, now_datetime

from textile_mill import reports_lib as rl
from textile_mill.dashboards import kpi as K
from textile_mill.dashboards import queries as Q
from textile_mill.dashboards import targets
from textile_mill.dashboards.common import run_widgets, report_route, route, table, tile, trend_widget, widget
from textile_mill.dashboards.filters import SLUG_STAGES, SLUG_TITLES, line_flows, line_stages

TILES = [
	("REVENUE", None, "Revenue", ("query-report", "Order Cost and Profitability")),
	("GROSS_MARGIN_PCT", None, "Gross Margin %", ("query-report", "Order Cost and Profitability")),
	("PRODUCTION_VALUE", None, "Production Value", ("query-report", "Production Cost per Unit")),
	("FINISHED_FABRIC_M", None, "Finished Fabric (m)", ("query-report", "Fabric Grade Analysis")),
	("GARMENTS_PCS", None, "Garments (pcs)", ("query-report", "Stage Yield Report")),
	("INVENTORY_VALUE", None, "Inventory Value", ("query-report", "Inventory Between Processes")),
	("ORDER_BOOK", None, "Order Book", ("List", "Sales Order")),
	("OTD_PCT", None, "On-Time Delivery %", ("List", "Delivery Note")),
]


def build(ctx) -> tuple[list, list]:
	tiles = []
	for code, stage, label, target in TILES:
		dd = report_route(target[1], ctx) if target[0] == "query-report" else route(target[0], target[1])
		tiles.append(tile(ctx, code, stage, label, drilldown=dd))
	widgets = [
		lambda: value_chain(ctx),
		lambda: trend_widget(ctx, "revenue_margin", "Revenue & Gross Margin (12 months)", 8,
			[("Revenue", "REVENUE", None), ("Gross Margin %", "GROSS_MARGIN_PCT", None)], kind="combo",
			drilldown=report_route("Order Cost and Profitability", ctx)),
		lambda: revenue_mix(ctx),
		lambda: top_customers(ctx),
		lambda: stage_cost_vs_standard(ctx),
		lambda: inventory_status(ctx),
		lambda: cash_gauges(ctx),
		lambda: alerts(ctx),
	]
	return tiles, run_widgets(widgets)


def _chain_node(ctx, slug: str, yields: dict, costs: dict) -> dict:
	stages = SLUG_STAGES[slug]
	main = next((s for s in reversed(stages) if s in yields), stages[-1])
	y = yields.get(main)
	yield_value = (y.yield_pct if y.yield_pct is not None else y.output_per_input * 100) if y else None
	status = targets.evaluate("STAGE_YIELD", yield_value, main, ctx.get("plant"), ctx.to_date)
	buffer = Q.stage_buffer(ctx, stages[0])
	cost = costs.get(main)
	return {
		"id": slug,
		"label": SLUG_TITLES[slug],
		"output": flt(y.output_qty) if y else 0,
		"uom": (y.output_uom if y else None),
		"yield_pct": yield_value,
		"yield_label": "pcs/100 m" if main == "Garments" else "yield",
		"status": status["status"] if status else "grey",
		"cost_per_unit": cost.actual_per_unit if cost else None,
		"wip_qty": buffer["qty"],
		"wip_uom": buffer["uom"],
		"route": f"/app/dm-stage/{slug}",
	}


def value_chain(ctx) -> dict:
	yields = {r.stage: r for r in rl.stage_yield_summary(Q.rf(ctx))}
	costs = {r.stage: r for r in rl.cost_per_unit_by_stage(Q.rf(ctx))}
	cache, rows = {}, []
	for title, slugs in line_flows(ctx.get("business_line")):
		nodes = [cache.setdefault(slug, _chain_node(ctx, slug, yields, costs)) for slug in slugs]
		links = [{"source": a["id"], "target": b["id"], "value": a["output"]} for a, b in zip(nodes, nodes[1:])]
		rows.append({"title": title, "nodes": nodes, "links": links})
	line = ctx.get("business_line") or "Denim"
	label = "Value Chain — all business lines" if line == "All" else f"{line} Value Chain"
	return widget("value_chain", "value_chain_flow", label, 12, {"rows": rows, "nodes": rows[0]["nodes"], "links": rows[0]["links"]},
		explain="Each box is a stage: output in the period, yield (colour = target status), cost per unit and quantity waiting. "
		"Switch the business line in the filter bar.")


def revenue_mix(ctx) -> dict:
	mix = {}
	for r in frappe.db.sql(
		"""select sii.item_code, sii.item_group, sum(sii.base_net_amount) v from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent where si.docstatus = 1 and si.company = %(company)s
		and si.posting_date between %(from_date)s and %(to_date)s group by sii.item_code, sii.item_group""",
		ctx,
		as_dict=True,
	):
		if r.item_group == "Finished Fabric":
			key = "Fabric A-grade" if r.item_code.endswith("-A") else "Fabric B / Rejected"
		elif r.item_group in ("Garments", "Garment WIP"):
			key = "Garments"
		elif r.item_group == "Waste":
			key = "Waste sales"
		else:
			key = "Other"
		mix[key] = mix.get(key, 0) + flt(r.v)
	return widget("revenue_mix", "donut", "Revenue Mix", 4,
		{"items": [{"name": k, "value": round(v, 2)} for k, v in sorted(mix.items(), key=lambda x: -x[1])], "format": "currency"},
		drilldown=route("query-report", "Sales Analytics"))


def top_customers(ctx) -> dict:
	sales = Q.sales_by(ctx, "customer")
	open_orders = dict(frappe.db.sql(
		"""select so.customer, sum((soi.stock_qty - soi.delivered_qty) * soi.base_rate / ifnull(nullif(soi.conversion_factor, 0), 1))
		from `tabSales Order Item` soi join `tabSales Order` so on so.name = soi.parent where so.docstatus = 1
		and so.company = %(company)s and so.status not in ('Closed', 'Completed') and soi.stock_qty > soi.delivered_qty
		group by so.customer""",
		ctx,
	))
	overdue = dict(frappe.db.sql(
		"""select customer, sum(outstanding_amount) from `tabSales Invoice` where docstatus = 1 and company = %(company)s
		and outstanding_amount > 0 and due_date < %(to_date)s group by customer""",
		ctx,
	))
	rows = []
	for customer, s in sorted(sales.items(), key=lambda x: -x[1].revenue)[:10]:
		rows.append({"customer": customer, "revenue": s.revenue, "margin_pct": s.margin_pct,
			"open_orders": flt(open_orders.get(customer)), "overdue": flt(overdue.get(customer)),
			"_status": {"overdue": "red" if flt(overdue.get(customer)) > 0 else None},
			"_route": {"customer": ["Form", "Customer", customer]}})
	return widget("top_customers", "table", "Top Customers", 6, table(
		[("Customer", "customer", "link"), ("Revenue", "revenue", "currency"), ("Margin %", "margin_pct", "percent"),
			("Open Orders", "open_orders", "currency"), ("Overdue", "overdue", "currency")], rows))


def stage_cost_vs_standard(ctx) -> dict:
	rows = {r.stage: r for r in rl.cost_per_unit_by_stage(Q.rf(ctx))}
	stages = [s for s in line_stages(ctx.get("business_line")) if s in rows]
	actual = [round(rows[s].actual_per_unit / rows[s].standard_per_unit * 100, 1) if rows[s].standard_per_unit else None for s in stages]
	return widget("stage_cost_std", "grouped_bar", "Stage Cost vs Standard (index, standard = 100)", 6,
		{"categories": stages, "series": [{"name": "Standard", "values": [100] * len(stages)}, {"name": "Actual", "values": actual}],
			"unit": "", "mark_line": 100},
		drilldown=report_route("Production Cost per Unit", ctx))


def inventory_status(ctx) -> dict:
	by_status = K.inventory_by_status(ctx, with_qty=True)
	total = sum(v["value"] for v in by_status.values()) or 1
	items = [{"name": s, "value": round(v["value"], 2), "pct": round(v["value"] / total * 100, 1),
		"route": ["query-report", "Stock Balance"]} for s, v in sorted(by_status.items(), key=lambda x: -x[1]["value"]) if v["value"]]
	return widget("inventory_status", "status_bars", "Inventory by Status", 4, {"items": items, "format": "currency"})


def cash_gauges(ctx) -> dict:
	cash = flt(K.cash_position(ctx)["value"])
	ar = flt(K.ar_overdue(ctx)["value"])
	ap = flt(K.ap_due_30(ctx)["value"])
	scale = max(abs(cash), ar, ap, 1) * 1.2
	return widget("cash_ar_ap", "gauge_group", "Cash, AR Overdue, AP Due ≤30 d", 4, {"gauges": [
		{"name": "Cash Position", "value": round(cash, 0), "max": scale, "format": "currency"},
		{"name": "AR Overdue", "value": round(ar, 0), "max": scale, "format": "currency", "status": "red" if ar else "green"},
		{"name": "AP Due ≤30 d", "value": round(ap, 0), "max": scale, "format": "currency"},
	]}, drilldown=route("query-report", "Accounts Receivable"))


def alerts(ctx) -> dict:
	items = []
	for r in rl.stage_yield_summary(Q.rf(ctx)):
		value = r.yield_pct
		status = targets.evaluate("STAGE_YIELD", value, r.stage, ctx.get("plant"), ctx.to_date) if value is not None else None
		if status and status["status"] == "red":
			items.append({"level": "red", "text": f"{r.stage} yield {value:.1f}% is below {status['red']}%",
				"route": ["query-report", "Stage Yield Report"]})
	for wo in frappe.db.sql(
		"""select name, production_item, planned_end_date from `tabWork Order` where docstatus = 1 and company = %(company)s
		and status in ('Not Started', 'In Process') and planned_end_date < %(cutoff)s order by planned_end_date limit 10""",
		{"company": ctx.company, "cutoff": add_days(now_datetime(), -2)},
		as_dict=True,
	):
		items.append({"level": "amber", "text": f"Work Order {wo.name} ({wo.production_item}) is more than 2 days late",
			"route": ["Form", "Work Order", wo.name]})
	for irl in frappe.get_all("Indigo Range Log", filters={"docstatus": 1, "status": "Out of Spec",
			"posting_date": ["between", [ctx.from_date, ctx.to_date]]}, fields=["name", "posting_date", "out_of_spec_count"]):
		items.append({"level": "red", "text": f"Indigo range {irl.name} on {irl.posting_date}: {irl.out_of_spec_count} reading(s) out of spec",
			"route": ["Form", "Indigo Range Log", irl.name]})
	for qi in frappe.get_all("Quality Inspection", filters={"docstatus": 1, "status": "Rejected",
			"report_date": ["between", [ctx.from_date, ctx.to_date]]}, fields=["name", "item_code", "reference_name"], limit=10):
		items.append({"level": "red", "text": f"Quality Inspection {qi.name} rejected {qi.item_code}",
			"route": ["Form", "Quality Inspection", qi.name]})
	for r in K.orders_at_risk(ctx)[:10]:
		items.append({"level": "amber", "text": f"{r.sales_order} ({r.customer}): {r.item_code} short {r.shortfall:,.0f} for {r.delivery_date}",
			"route": ["Form", "Sales Order", r.sales_order]})
	absorbed = rl.absorbed_utilities(ctx.company, ctx.from_date, ctx.to_date)
	actual = rl.actual_utilities(ctx.company, ctx.from_date, ctx.to_date)
	for stage in sorted(set(absorbed) | set(actual)):
		a, b = flt(actual.get(stage)), flt(absorbed.get(stage))
		if a and abs(b - a) / a > 0.10:
			items.append({"level": "amber", "text": f"{stage}: utility absorbed vs actual off by {(b - a) / a * 100:+.0f}%",
				"route": ["query-report", "Utility Absorption vs Actual"]})
	order = {"red": 0, "amber": 1, "green": 2}
	items.sort(key=lambda x: order.get(x["level"], 3))
	return widget("alerts", "alert_list", "Alerts", 8, {"items": items[:25], "empty": "No alerts — all KPIs within tolerance."})
