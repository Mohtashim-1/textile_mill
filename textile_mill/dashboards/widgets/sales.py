"""D5 Sales & Orders (CEO, Sales Manager)."""

from collections import defaultdict

import frappe
from frappe.utils import add_days, add_months, flt, get_first_day, getdate

from textile_mill.dashboards import kpi as K
from textile_mill.dashboards.common import run_widgets, monthly_trend, route, table, tile, widget

STATUSES = ("Not started", "In production", "Ready", "Partially delivered")


def build(ctx) -> tuple[list, list]:
	garments = K.price_realisation(ctx, ("Garments",))["value"]
	tiles = [
		tile(ctx, "ORDER_BOOK", label="Order Book", drilldown=route("List", "Sales Order", status=["not in", ["Closed", "Completed"]])),
		tile(ctx, "BOOKED", label="Booked (period)", drilldown=route("List", "Sales Order")),
		tile(ctx, "DELIVERED", label="Delivered (period)", drilldown=route("List", "Delivery Note")),
		tile(ctx, "OTD_PCT", label="On-Time Delivery %", drilldown=route("List", "Delivery Note")),
		tile(ctx, "ORDERS_AT_RISK", label="Orders at Risk", compare=False),
		dict(tile(ctx, "PRICE_REALISATION_FABRIC", label="Avg Price — Fabric (PKR/m)", drilldown=route("query-report", "Sales Analytics")),
			subtitle=f"Garments PKR {garments:,.0f}/pc" if garments else None),
	]
	lines = open_lines(ctx)
	widgets = [
		lambda: booking_trend(ctx),
		lambda: order_status(lines),
		lambda: delivery_calendar(ctx, lines),
		lambda: at_risk(ctx),
		lambda: price_trend(ctx),
		lambda: customer_mix(ctx),
		lambda: b_grade_recovery(ctx),
	]
	return tiles, run_widgets(widgets)


def open_lines(ctx) -> list[dict]:
	rows = frappe.db.sql(
		"""select so.name, so.customer, soi.item_code, soi.delivery_date, soi.stock_qty, soi.delivered_qty,
			(soi.stock_qty - soi.delivered_qty) * soi.base_rate / ifnull(nullif(soi.conversion_factor, 0), 1) pending_value
		from `tabSales Order Item` soi join `tabSales Order` so on so.name = soi.parent where so.docstatus = 1
		and so.company = %(company)s and so.status not in ('Closed', 'Completed', 'On Hold') and soi.stock_qty > soi.delivered_qty""",
		ctx,
		as_dict=True,
	)
	for r in rows:
		pending = flt(r.stock_qty) - flt(r.delivered_qty)
		available = flt(frappe.db.sql("select sum(actual_qty) from `tabBin` where item_code = %s", r.item_code)[0][0])
		in_production = frappe.db.exists("Work Order", {"production_item": r.item_code, "docstatus": 1, "status": ["in", ["Not Started", "In Process"]]})
		if flt(r.delivered_qty):
			r.status = "Partially delivered"
		elif available >= pending:
			r.status = "Ready"
		elif in_production:
			r.status = "In production"
		else:
			r.status = "Not started"
		r.ready = available >= pending
	return rows


def booking_trend(ctx) -> dict:
	labels, booked = monthly_trend(ctx, "BOOKED")
	_l, delivered = monthly_trend(ctx, "DELIVERED")
	_l, otd = monthly_trend(ctx, "OTD_PCT")
	return widget("booking_trend", "combo", "Bookings, Deliveries & OTD (12 months)", 8,
		{"categories": labels, "series": [{"name": "Booked", "values": booked, "type": "bar"},
			{"name": "Delivered", "values": delivered, "type": "bar"}, {"name": "OTD %", "values": otd, "type": "line", "axis": 1}],
			"format": "currency"}, synthetic=bool(ctx.get("synthetic")))


def order_status(lines) -> dict:
	data = defaultdict(float)
	customers = sorted({r.customer for r in lines})
	for r in lines:
		data[(r.customer, r.status)] += flt(r.pending_value)
	return widget("order_status", "stacked_bar", "Open Orders by Status (value)", 4,
		{"categories": customers, "series": [{"name": s, "values": [round(data[(c, s)], 0) for c in customers], "stack": "s"} for s in STATUSES],
			"format": "currency", "horizontal": True}, drilldown=route("List", "Sales Order"),
		note=None if lines else "No open sales orders.")


def delivery_calendar(ctx, lines) -> dict:
	start = getdate(ctx.to_date)
	days = []
	for i in range(30):
		d = add_days(start, i)
		due = [r for r in lines if getdate(r.delivery_date) == d]
		if not due:
			status = None
		elif all(r.ready for r in due):
			status = "green"
		elif any(r.ready for r in due):
			status = "amber"
		else:
			status = "red"
		days.append({"date": str(d), "label": d.strftime("%d"), "dow": d.strftime("%a"), "count": len(due), "status": status,
			"tooltip": "; ".join(f"{r.name} {r.item_code}" for r in due)})
	return widget("delivery_calendar", "calendar_strip", "Delivery Calendar — next 30 days", 12, {"days": days})


def at_risk(ctx) -> dict:
	rows = []
	for r in K.orders_at_risk(ctx):
		rows.append({"sales_order": r.sales_order, "customer": r.customer, "item_code": r.item_code, "due": r.delivery_date,
			"required": r.required, "available": r.available, "shortfall": r.shortfall, "stage": r.stage,
			"_status": {"shortfall": "red"}, "_route": {"sales_order": ["Form", "Sales Order", r.sales_order]}})
	return widget("at_risk", "table", "Orders at Risk", 12, table(
		[("Sales Order", "sales_order", "link"), ("Customer", "customer"), ("Item", "item_code"), ("Due", "due", "date"),
			("Required", "required", "float"), ("On hand + WIP", "available", "float"), ("Shortfall", "shortfall", "float"),
			("Bottleneck Stage", "stage")], rows),
		note=None if rows else "No open order lines are short of stock and work in progress.")


def price_trend(ctx) -> dict:
	end = getdate(ctx.to_date)
	start = add_months(get_first_day(end), -11)
	rows = frappe.db.sql(
		"""select date_format(si.posting_date, '%%Y-%%m') m, case when sii.item_group = 'Garments' then 'Garments (PKR/pc)'
			when sii.item_code like '%%-A' then 'Fabric A (PKR/m)' else 'Fabric B/R (PKR/m)' end grp,
			sum(sii.base_net_amount) / sum(sii.stock_qty) price
		from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent where si.docstatus = 1
		and si.company = %(company)s and si.posting_date between %(start)s and %(end)s
		and sii.item_group in ('Finished Fabric', 'Garments') group by m, grp""",
		{"company": ctx.company, "start": start, "end": end},
		as_dict=True,
	)
	months = [add_months(start, i) for i in range(12)]
	keys = [m.strftime("%Y-%m") for m in months]
	data = {(r.m, r.grp): round(flt(r.price), 0) for r in rows}
	groups = ("Fabric A (PKR/m)", "Fabric B/R (PKR/m)", "Garments (PKR/pc)")
	return widget("price_trend", "line", "Price Realisation by Grade", 6,
		{"categories": [m.strftime("%b %y") for m in months], "series": [{"name": g, "values": [data.get((k, g)) for k in keys]} for g in groups],
			"format": "currency", "points": True})


def customer_mix(ctx) -> dict:
	rows = frappe.db.sql("""select customer, sum(base_net_total) v from `tabSales Invoice` where docstatus = 1 and company = %(company)s
		and posting_date between %(from_date)s and %(to_date)s group by customer order by v desc""", ctx)
	items = [{"name": c, "value": round(flt(v), 0)} for c, v in rows[:8]]
	if len(rows) > 8:
		items.append({"name": "Others", "value": round(sum(flt(v) for _c, v in rows[8:]), 0)})
	return widget("customer_mix", "donut", "Revenue by Customer", 6, {"items": items, "format": "currency"},
		drilldown=route("query-report", "Sales Analytics"))


def b_grade_recovery(ctx) -> dict:
	items = frappe.get_all("Item", filters={"item_group": "Finished Fabric", "name": ["not like", "%-A"]}, pluck="name")
	a_price = K.price_realisation(ctx, ("Finished Fabric",))["value"]
	a_items = frappe.get_all("Item", filters={"item_group": "Finished Fabric", "name": ["like", "%-A"]}, pluck="name")
	if a_items:
		row = frappe.db.sql("""select sum(sii.base_net_amount) / sum(sii.stock_qty) from `tabSales Invoice Item` sii join `tabSales Invoice` si
			on si.name = sii.parent where si.docstatus = 1 and si.company = %(company)s and sii.item_code in %(items)s
			and si.posting_date between %(from_date)s and %(to_date)s""", {**ctx, "items": tuple(a_items)})
		a_price = flt(row[0][0]) or a_price
	rows = []
	for item in items:
		produced = flt(frappe.db.sql("""select sum(sle.actual_qty) from `tabStock Ledger Entry` sle join `tabStock Entry` se on se.name = sle.voucher_no
			where sle.voucher_type = 'Stock Entry' and sle.is_cancelled = 0 and sle.actual_qty > 0 and se.purpose = 'Repack'
			and sle.item_code = %(item)s and sle.posting_date between %(from_date)s and %(to_date)s""", {**ctx, "item": item})[0][0])
		sold = frappe.db.sql("""select sum(sii.stock_qty), sum(sii.base_net_amount) from `tabSales Invoice Item` sii join `tabSales Invoice` si
			on si.name = sii.parent where si.docstatus = 1 and sii.item_code = %(item)s and si.posting_date between %(from_date)s and %(to_date)s""",
			{**ctx, "item": item})[0]
		unsold = frappe.db.sql("select sum(actual_qty), sum(stock_value) from `tabBin` where item_code = %s", item)[0]
		price = flt(sold[1]) / flt(sold[0]) if flt(sold[0]) else None
		rows.append({"item_code": item, "produced": produced, "sold": flt(sold[0]), "unsold_qty": flt(unsold[0]), "unsold_value": flt(unsold[1]),
			"realisation_pct": price / a_price * 100 if price and a_price else None, "_route": {"item_code": ["Form", "Item", item]}})
	return widget("b_grade_recovery", "table", "B-grade & Rejected Recovery", 12, table(
		[("Item", "item_code", "link"), ("Produced (m)", "produced", "float"), ("Sold (m)", "sold", "float"),
			("Unsold (m)", "unsold_qty", "float"), ("Unsold Value", "unsold_value", "currency"),
			("Price vs A-grade %", "realisation_pct", "percent")], rows))
