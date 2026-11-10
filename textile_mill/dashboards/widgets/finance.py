"""D3 Cost & Finance (CFO)."""

from collections import defaultdict

import frappe
from frappe.utils import add_days, date_diff, flt, getdate

from textile_mill import reports_lib as rl
from textile_mill.constants import STAGE_COST_CENTER
from textile_mill.dashboards.filters import line_stages
from textile_mill.dashboards import kpi as K
from textile_mill.dashboards import queries as Q
from textile_mill.dashboards.common import run_widgets, monthly_trend, report_route, route, table, tile, widget

COST_TILES = [
	("Spinning", "Cost / kg Yarn"),
	("Indigo Dyeing", "Cost / kg Indigo Yarn"),
	("Finishing", "Cost / m Finished Fabric"),
	("Garments", "Cost / pc Garment"),
]
PRICE_ITEMS = ("CW-PRE", "CW-POST", "VC-RAW", "CHM-IND", "CHM-HYD", "CHM-SBLK")


def build(ctx) -> tuple[list, list]:
	costs = {r.stage: r for r in rl.cost_per_unit_by_stage(Q.rf(ctx))}
	tiles = []
	for stage, label in COST_TILES:
		row = costs.get(stage)
		tiles.append(tile(ctx, "COST_PER_UNIT", stage, label, drilldown=report_route("Production Cost per Unit", ctx, dm_stage=stage),
			show_standard={"value": row.standard_per_unit, "label": "Std"} if row else None))
	tiles += [
		tile(ctx, "GROSS_MARGIN_PCT", label="Gross Margin %", drilldown=report_route("Order Cost and Profitability", ctx)),
		tile(ctx, "STD_VARIANCE_AMOUNT", label="Std Cost Variance", drilldown=report_route("Production Cost per Unit", ctx)),
		tile(ctx, "UTILITY_VARIANCE", label="Utility Absorbed − Actual", drilldown=report_route("Utility Absorption vs Actual", ctx)),
		tile(ctx, "WIP_VALUE", label="WIP Value", drilldown=report_route("Inventory Between Processes", ctx)),
	]
	widgets = [
		lambda: cost_trend(ctx),
		lambda: cost_breakup(ctx),
		lambda: variance_waterfall(ctx),
		lambda: budget_vs_actual(ctx),
		lambda: product_profitability(ctx),
		lambda: customer_profitability(ctx),
		lambda: inventory_category(ctx),
		lambda: ar_ap_aging(ctx),
		lambda: cash_trend(ctx),
		lambda: waste_recovery(ctx),
	]
	return tiles, run_widgets(widgets)


def cost_trend(ctx) -> dict:
	out, labels = [], []
	for stage in ("Spinning", "Indigo Dyeing", "Finishing", "Garments"):
		labels, values = monthly_trend(ctx, "COST_PER_UNIT", stage)
		base = next((v for v in values if v), None)
		out.append({"name": stage, "values": [round(v / base * 100, 1) if (v and base) else None for v in values]})
	return widget("cost_trend", "line", "Cost per Unit Trend (index, first month = 100)", 6,
		{"categories": labels, "series": out, "unit": "", "mark_line": 100}, synthetic=bool(ctx.get("synthetic")))


def cost_breakup(ctx) -> dict:
	agg = defaultdict(lambda: defaultdict(float))
	for r in rl.manufacture_entries(Q.rf(ctx)):
		a = agg[r.dm_stage]
		a["qty"] += flt(r.output_qty)
		a["Material"] += flt(r.material_cost)
		a["Operating"] += flt(r.operating_cost)
		a["Utilities"] += flt(r.utilities_absorbed)
		a["Corrective"] += flt(r.corrective_cost)
		a["Scrap credit"] -= flt(r.scrap_value)
	stages = [s for s in line_stages(ctx.get("business_line")) if agg[s]["qty"]]
	parts = ("Material", "Operating", "Utilities", "Corrective", "Scrap credit")
	return widget("cost_breakup", "stacked_bar", "Cost Build-up per Unit by Stage", 6,
		{"categories": stages, "series": [{"name": p, "values": [round(agg[s][p] / agg[s]["qty"], 2) for s in stages], "stack": "c"}
			for p in parts], "format": "currency"},
		drilldown=report_route("Production Cost per Unit", ctx))


def variance_waterfall(ctx) -> dict:
	rows = rl.cost_per_unit(Q.rf(ctx))
	standard = sum(flt(r.standard_per_unit) * flt(r.output_qty) for r in rows)
	actual = sum(flt(r.total_actual_cost) for r in rows)
	chem = sum(flt(r.get("variance_amount")) for r in rl.recipe_variance(Q.rf(ctx)) if not r.get("is_total"))
	corrective = sum(flt(r.cost) for r in rl.corrective_jobs(Q.rf(ctx)))
	price = _material_price_variance(ctx)
	fabric_rate = flt(frappe.db.get_value("Item Price", {"item_code": "FF-DM1150-A", "buying": 1}, "price_list_rate")) or 0
	cut_m = flt(frappe.db.sql("""select sum(cutting_variance_m) from `tabCut Plan` where docstatus = 1 and company = %(company)s
		and posting_date between %(from_date)s and %(to_date)s""", ctx)[0][0])
	cutting = cut_m * (fabric_rate or flt(frappe.db.get_value("Item", "FF-DM1150-A", "valuation_rate")))
	usage = actual - standard - price - chem - corrective - cutting
	steps = [("Material price", price), ("Usage / yield", usage), ("Chemical", chem), ("Corrective", corrective), ("Cutting", cutting)]
	return widget("variance_waterfall", "waterfall", "Standard → Actual Cost (period)", 6,
		{"start": {"name": "Standard", "value": round(standard, 0)}, "steps": [{"name": n, "value": round(v, 0)} for n, v in steps],
			"end": {"name": "Actual", "value": round(actual, 0)}, "format": "currency"},
		explain="Usage / yield is the residual after price, chemical, corrective and cutting variances, so the bridge always closes.")


def _material_price_variance(ctx) -> float:
	"""(actual rate − standard buying rate) × qty for purchased materials consumed in manufacture."""
	total = 0.0
	for r in frappe.db.sql(
		"""select d.item_code, sum(d.transfer_qty) qty, sum(d.amount) amount from `tabStock Entry Detail` d
		join `tabStock Entry` se on se.name = d.parent where se.docstatus = 1 and se.purpose = 'Manufacture'
		and se.company = %(company)s and se.posting_date between %(from_date)s and %(to_date)s and ifnull(d.s_warehouse, '') != ''
		and d.item_code in (select name from `tabItem` where dm_stage = 'Raw') group by d.item_code""",
		ctx,
		as_dict=True,
	):
		std = rl.standard_cost(r.item_code)
		if std and flt(r.qty):
			total += flt(r.amount) - std * flt(r.qty)
	return total


def budget_vs_actual(ctx) -> dict:
	months = max(date_diff(ctx.to_date, ctx.from_date) + 1, 1) / 365 * 12
	budgets = defaultdict(float)
	for r in frappe.db.sql(
		"""select b.cost_center, sum(ba.budget_amount) amt from `tabBudget` b join `tabBudget Account` ba on ba.parent = b.name
		where b.docstatus = 1 and b.company = %(company)s and b.budget_against = 'Cost Center' group by b.cost_center""",
		ctx,
		as_dict=True,
	):
		budgets[r.cost_center] += flt(r.amt) / 12 * months
	actual = defaultdict(float)
	for cost_center, absorbed, direct in frappe.db.sql(
		"""select gle.cost_center,
			sum(if(a.account_type = 'Expenses Included In Valuation' or a.name in (select distinct expense_account
				from `tabLanded Cost Taxes and Charges` where parenttype = 'Stock Entry'), gle.credit - gle.debit, 0)),
			sum(if(a.account_type in ('Expenses Included In Valuation', 'Cost of Goods Sold', 'Stock Adjustment') or a.name in
				(select distinct expense_account from `tabLanded Cost Taxes and Charges` where parenttype = 'Stock Entry'), 0, gle.debit - gle.credit))
		from `tabGL Entry` gle join `tabAccount` a on a.name = gle.account
		where gle.is_cancelled = 0 and gle.company = %(company)s and a.root_type = 'Expense' and ifnull(gle.cost_center, '') != ''
		and gle.posting_date between %(from_date)s and %(to_date)s group by gle.cost_center""",
		ctx,
	):
		actual[cost_center] += flt(absorbed) + flt(direct)
	abbr = frappe.get_cached_value("Company", ctx.company, "abbr")
	centers = [f"{c} - {abbr}" for c in dict.fromkeys(STAGE_COST_CENTER[s] for s in line_stages(ctx.get("business_line")))] + [f"Utilities & Admin - {abbr}"]
	centers = [c for c in centers if budgets.get(c) or actual.get(c)]
	return widget("budget_vs_actual", "grouped_bar", "Budget vs Actual by Cost Center (period, pro-rata)", 6,
		{"categories": [c.rsplit(" - ", 1)[0] for c in centers], "series": [
			{"name": "Budget", "values": [round(budgets.get(c, 0), 0) for c in centers]},
			{"name": "Actual", "values": [round(flt(actual.get(c)), 0) for c in centers]}], "format": "currency"},
		drilldown=route("query-report", "Budget Variance Report"), note=None if budgets else "No budgets set up yet.",
		explain="Actual = conversion cost absorbed into production (operating + utilities) plus direct expenses booked to the cost center.")


def product_profitability(ctx) -> dict:
	points = []
	for item, s in Q.sales_by(ctx, "item_code").items():
		if s.revenue:
			points.append({"name": item, "x": round(s.revenue, 0), "y": round(flt(s.margin_pct), 1), "size": s.qty,
				"route": ["query-report", "Order Cost and Profitability"]})
	return widget("product_profitability", "scatter", "Product Profitability (revenue vs margin %)", 6,
		{"points": points, "x_label": "Revenue", "y_label": "Margin %", "x_format": "currency"})


def customer_profitability(ctx) -> dict:
	sales = Q.sales_by(ctx, "customer")
	days = date_diff(ctx.to_date, ctx.from_date) + 1
	outstanding = dict(frappe.db.sql("""select customer, sum(outstanding_amount) from `tabSales Invoice` where docstatus = 1
		and company = %(company)s group by customer""", ctx))
	overdue = dict(frappe.db.sql("""select customer, sum(outstanding_amount) from `tabSales Invoice` where docstatus = 1
		and company = %(company)s and outstanding_amount > 0 and due_date < %(to_date)s group by customer""", ctx))
	rows = []
	for c, s in sorted(sales.items(), key=lambda x: -x[1].revenue):
		rows.append({"customer": c, "revenue": s.revenue, "cogs": s.cogs, "margin": s.margin, "margin_pct": s.margin_pct,
			"dso": flt(outstanding.get(c)) / s.revenue * days if s.revenue else None, "overdue": flt(overdue.get(c)),
			"_status": {"overdue": "red" if flt(overdue.get(c)) else None}, "_route": {"customer": ["Form", "Customer", c]}})
	return widget("customer_profitability", "table", "Customer Profitability", 6, table(
		[("Customer", "customer", "link"), ("Revenue", "revenue", "currency"), ("COGS", "cogs", "currency"),
			("Margin", "margin", "currency"), ("Margin %", "margin_pct", "percent"), ("DSO", "dso", "int"),
			("Overdue", "overdue", "currency")], rows))


def inventory_category(ctx) -> dict:
	return widget("inventory_category", "donut", "Inventory Value by Category", 4,
		{"items": [{"name": k, "value": round(v, 0)} for k, v in Q.inventory_by_category(ctx)], "format": "currency"},
		drilldown=route("query-report", "Stock Balance"))


def ar_ap_aging(ctx) -> dict:
	buckets = ("Not due", "0–30", "31–60", "61–90", "90+")

	def bucketise(doctype):
		out = defaultdict(float)
		for due, amt in frappe.db.sql(
			f"""select due_date, outstanding_amount from `tab{doctype}` where docstatus = 1 and company = %(company)s
			and outstanding_amount > 0""",  # noqa: S608
			ctx,
		):
			late = date_diff(ctx.to_date, due)
			key = "Not due" if late <= 0 else "0–30" if late <= 30 else "31–60" if late <= 60 else "61–90" if late <= 90 else "90+"
			out[key] += flt(amt)
		return [round(out[b], 0) for b in buckets]

	return widget("ar_ap_aging", "grouped_bar", "Receivables & Payables Aging", 4,
		{"categories": list(buckets), "series": [{"name": "Receivable", "values": bucketise("Sales Invoice")},
			{"name": "Payable", "values": bucketise("Purchase Invoice")}], "format": "currency"},
		drilldown=route("query-report", "Accounts Receivable"))


def cash_trend(ctx) -> dict:
	end = getdate(ctx.to_date)
	start = add_days(end, -59)
	opening = flt(frappe.db.sql("""select sum(gle.debit - gle.credit) from `tabGL Entry` gle join `tabAccount` a on a.name = gle.account
		where gle.is_cancelled = 0 and gle.company = %(company)s and a.account_type in ('Bank', 'Cash')
		and gle.posting_date < %(start)s""", {"company": ctx.company, "start": start})[0][0])
	moves = dict(frappe.db.sql("""select gle.posting_date, sum(gle.debit - gle.credit) from `tabGL Entry` gle
		join `tabAccount` a on a.name = gle.account where gle.is_cancelled = 0 and gle.company = %(company)s
		and a.account_type in ('Bank', 'Cash') and gle.posting_date between %(start)s and %(end)s group by gle.posting_date""",
		{"company": ctx.company, "start": start, "end": end}))
	labels, values, running = [], [], opening
	for i in range(60):
		d = add_days(start, i)
		running += flt(moves.get(d))
		labels.append(d.strftime("%d %b"))
		values.append(round(running, 0))
	return widget("cash_trend", "line", "Cash Position — last 60 days", 4,
		{"categories": labels, "series": [{"name": "Cash & Bank", "values": values, "area": True}], "format": "currency"},
		drilldown=route("query-report", "General Ledger"))


def waste_recovery(ctx) -> dict:
	generated = dict(frappe.db.sql("""select d.item_code, sum(d.transfer_qty) from `tabStock Entry Detail` d
		join `tabStock Entry` se on se.name = d.parent where se.docstatus = 1 and se.company = %(company)s and d.is_scrap_item = 1
		and se.posting_date between %(from_date)s and %(to_date)s group by d.item_code""", ctx))
	sold = {r.item_code: r for r in frappe.db.sql("""select sii.item_code, sum(sii.stock_qty) qty, sum(sii.base_net_amount) value
		from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent where si.docstatus = 1
		and si.company = %(company)s and si.posting_date between %(from_date)s and %(to_date)s and sii.item_group = 'Waste'
		group by sii.item_code""", ctx, as_dict=True)}
	unsold = dict(frappe.db.sql("""select b.item_code, sum(b.stock_value) from `tabBin` b join `tabItem` i on i.name = b.item_code
		where i.item_group = 'Waste' group by b.item_code"""))
	items = sorted(set(generated) | set(sold) | set(unsold))
	rows = [{"item_code": i, "generated": flt(generated.get(i)), "sold_qty": flt(sold[i].qty) if i in sold else 0,
		"sold_value": flt(sold[i].value) if i in sold else 0, "unsold_value": flt(unsold.get(i)),
		"_route": {"item_code": ["Form", "Item", i]}} for i in items]
	return widget("waste_recovery", "table", "Waste Recovery", 6, table(
		[("Waste Item", "item_code", "link"), ("Generated (kg)", "generated", "float"), ("Sold (kg)", "sold_qty", "float"),
			("Sales Value", "sold_value", "currency"), ("Unsold Stock Value", "unsold_value", "currency")], rows))
