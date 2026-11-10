"""D4 Quality & Inventory (shared by Production Director and CFO)."""

from collections import defaultdict

import frappe
from frappe.utils import add_days, date_diff, flt, getdate

from textile_mill import reports_lib as rl
from textile_mill.dashboards import kpi as K
from textile_mill.dashboards import queries as Q
from textile_mill.dashboards.common import run_widgets, daily_trend, report_route, route, table, tile, widget
from textile_mill.dashboards.widgets.finance import inventory_category

SHADE_STAGES = ("Fiber Dyeing", "Indigo Dyeing")
EXPIRY_HORIZON_DAYS = 60


def build(ctx) -> tuple[list, list]:
	tiles = [
		tile(ctx, "ACTIVE_ITEMS", label="Active Items in Stock", drilldown=route("query-report", "Stock Balance"), compare=False),
		tile(ctx, "INVENTORY_VALUE", label="Stock Value", drilldown=route("query-report", "Stock Balance")),
		tile(ctx, "FIRST_PASS_QI", label="First-pass QI %", drilldown=route("List", "Quality Inspection")),
		tile(ctx, "A_GRADE_PCT", label="A-Grade %", drilldown=report_route("Fabric Grade Analysis", ctx)),
		tile(ctx, "REDYE_PCT", label="Re-dye %", drilldown=report_route("Corrective Report", ctx)),
		tile(ctx, "LOW_STOCK_COUNT", label="Low-stock Items", compare=False, drilldown=route("List", "Item")),
		tile(ctx, "AGED_STOCK_VALUE", label="Aged Stock > 90 d", compare=False, drilldown=route("query-report", "Stock Ageing")),
		tile(ctx, "INVENTORY_ACCURACY", label="Inventory Accuracy %", drilldown=route("List", "Stock Reconciliation")),
	]
	widgets = [
		lambda: inventory_category(ctx),
		lambda: stock_value_trend(ctx),
		lambda: inventory_status_qty(ctx),
		lambda: attention_items(ctx),
		lambda: top_consumed(ctx),
		lambda: batch_trace_recent(ctx),
		lambda: expiring_batches(ctx),
		lambda: accuracy_gauge(ctx),
		lambda: grade_split(ctx),
		lambda: defect_pareto(ctx),
		lambda: qi_failures(ctx),
		lambda: shade_trend(ctx),
		lambda: aging_buckets(ctx),
	]
	return tiles, run_widgets(widgets)


def stock_value_trend(ctx) -> dict:
	labels, total = daily_trend(ctx, "INVENTORY_VALUE", days=30)
	_labels, wip = daily_trend(ctx, "WIP_VALUE", days=30)
	usable = [round(t - (w or 0), 0) if t is not None else None for t, w in zip(total, wip, strict=False)]
	return widget("stock_value_trend", "line", "Stock Value — last 30 days", 4,
		{"categories": labels, "series": [{"name": "Total", "values": total}, {"name": "Excl. WIP", "values": usable}],
			"format": "currency"}, synthetic=bool(ctx.get("synthetic")))


def inventory_status_qty(ctx) -> dict:
	by_status = K.inventory_by_status(ctx, with_qty=True)
	total = sum(v["value"] for v in by_status.values()) or 1
	items = [{"name": s, "value": round(v["value"], 0), "qty": round(v["qty"], 1), "pct": round(v["value"] / total * 100, 1)}
		for s, v in sorted(by_status.items(), key=lambda x: -x[1]["value"]) if v["value"] or v["qty"]]
	return widget("inventory_status", "status_bars", "Inventory Status", 4, {"items": items, "format": "currency", "show_qty": True},
		drilldown=report_route("Inventory Between Processes", ctx))


def attention_items(ctx) -> dict:
	rows = []
	for r in K.low_stock_rows(ctx):
		rows.append({"item_code": r.item_code, "item_name": r.item_name, "warehouse": r.warehouse, "qty": r.actual_qty,
			"level": r.warehouse_reorder_level, "issue": "Out of stock" if not flt(r.actual_qty) else "Below reorder level",
			"reorder_qty": r.warehouse_reorder_qty, "_status": {"issue": "red" if not flt(r.actual_qty) else "amber"},
			"_action": {"label": "Create Material Request", "method": "textile_mill.dashboards.api.create_material_request",
				"args": {"item_code": r.item_code, "warehouse": r.warehouse, "qty": r.warehouse_reorder_qty}, "role": "Stock Manager"}})
	horizon = add_days(ctx.to_date, EXPIRY_HORIZON_DAYS)
	for b in K.batch_balances(ctx):
		if b.expiry_date and getdate(b.expiry_date) <= getdate(horizon):
			rows.append({"item_code": b.item_code, "warehouse": b.warehouse, "qty": b.qty, "issue": f"Batch {b.batch_no} expires {b.expiry_date}",
				"_status": {"issue": "red" if getdate(b.expiry_date) <= getdate(ctx.to_date) else "amber"}})
		elif date_diff(ctx.to_date, b.manufacturing_date or b.created) > 90:
			rows.append({"item_code": b.item_code, "warehouse": b.warehouse, "qty": b.qty, "issue": f"Batch {b.batch_no} aged > 90 d",
				"_status": {"issue": "amber"}})
	for r in rows:
		r.setdefault("_route", {"item_code": ["Form", "Item", r["item_code"]]})
	return widget("attention_items", "table", "Items Needing Attention", 8, table(
		[("Item", "item_code", "link"), ("Name", "item_name"), ("Warehouse", "warehouse"), ("Qty", "qty", "float"),
			("Reorder Level", "level", "float"), ("Issue", "issue")], rows[:50]),
		note=None if rows else "Nothing below reorder level, expiring or aged.")


def top_consumed(ctx) -> dict:
	def consumed(start, end):
		return dict(frappe.db.sql("""select sle.item_code, -sum(sle.actual_qty) from `tabStock Ledger Entry` sle
			join `tabStock Entry` se on se.name = sle.voucher_no where sle.voucher_type = 'Stock Entry' and sle.is_cancelled = 0
			and sle.actual_qty < 0 and se.purpose = 'Manufacture' and se.company = %(company)s
			and sle.posting_date between %(start)s and %(end)s group by sle.item_code""",
			{"company": ctx.company, "start": start, "end": end}))

	now = consumed(ctx.from_date, ctx.to_date)
	prev = consumed(ctx.compare_from, ctx.compare_until) if ctx.get("compare_from") else {}
	rows = []
	for item, qty in sorted(now.items(), key=lambda x: -x[1])[:10]:
		p = flt(prev.get(item))
		rows.append({"item_code": item, "uom": frappe.get_cached_value("Item", item, "stock_uom"), "qty": qty, "previous": p,
			"change_pct": (qty - p) / p * 100 if p else None, "_route": {"item_code": ["Form", "Item", item]}})
	return widget("top_consumed", "table", "Top Consumed Items vs Previous Period", 4, table(
		[("Item", "item_code", "link"), ("UOM", "uom"), ("This period", "qty", "float"), ("Previous", "previous", "float"),
			("Change %", "change_pct", "percent")], rows))


def batch_trace_recent(ctx) -> dict:
	batches = frappe.get_all("Batch", filters={"manufacturing_date": ["<=", ctx.to_date]},
		fields=["name", "item", "batch_qty", "manufacturing_date"], order_by="manufacturing_date desc, creation desc", limit=15)
	rows = []
	for b in batches:
		loc = frappe.db.sql("""select e.warehouse from `tabSerial and Batch Entry` e join `tabSerial and Batch Bundle` sb on sb.name = e.parent
			where e.batch_no = %s and sb.docstatus = 1 and sb.is_cancelled = 0 group by e.warehouse having sum(e.qty) > 0 limit 1""", b.name)
		qi = frappe.db.get_value("Quality Inspection", {"batch_no": b.name, "docstatus": 1}, "status", order_by="creation desc")
		grade = frappe.db.get_value("Fabric Roll", {"batch_no": b.name}, "grade")
		rows.append({"batch": b.name, "item": b.item, "stage": frappe.get_cached_value("Item", b.item, "dm_stage"), "qty": b.batch_qty,
			"location": loc[0][0] if loc else "Consumed / shipped", "qi": qi or "—", "grade": grade or "",
			"_status": {"qi": "red" if qi == "Rejected" else ("green" if qi == "Accepted" else None)},
			"_route": {"batch": ["query-report", "Batch Genealogy", {"batch_no": b.name}]}})
	return widget("batch_trace", "table", "Recent Batches — click to trace genealogy", 8, table(
		[("Batch", "batch", "link"), ("Item", "item"), ("Stage", "stage"), ("Qty", "qty", "float"), ("Location", "location"),
			("QI", "qi"), ("Grade", "grade")], rows))


def expiring_batches(ctx) -> dict:
	horizon = add_days(ctx.to_date, EXPIRY_HORIZON_DAYS)
	rows = [{"batch": b.batch_no, "item": b.item_code, "warehouse": b.warehouse, "qty": b.qty, "expiry": b.expiry_date,
		"days": date_diff(b.expiry_date, ctx.to_date), "_route": {"batch": ["Form", "Batch", b.batch_no]}}
		for b in K.batch_balances(ctx) if b.expiry_date and getdate(b.expiry_date) <= getdate(horizon)]
	rows.sort(key=lambda r: r["days"])
	return widget("expiring", "table", f"Expiring within {EXPIRY_HORIZON_DAYS} days (chemicals, sizing)", 4, table(
		[("Batch", "batch", "link"), ("Item", "item"), ("Warehouse", "warehouse"), ("Qty", "qty", "float"), ("Expiry", "expiry", "date"),
			("Days", "days", "int")], rows), note=None if rows else "No batches expiring soon.")


def accuracy_gauge(ctx) -> dict:
	value = K.inventory_accuracy(ctx)["value"]
	return widget("accuracy", "gauge", "Inventory Accuracy", 4, {"value": round(value, 1) if value is not None else None, "max": 100,
		"format": "percent", "bands": [[95, "red"], [98, "amber"], [100, "green"]]},
		note=None if value is not None else "No stock counts (Stock Reconciliation) in the period.")


def grade_split(ctx) -> dict:
	g = rl.grade_split(Q.rf(ctx))
	return widget("grade_split", "donut", "Fabric Grade Split (m)", 4, {"items": [
		{"name": "A", "value": round(g["A"], 1), "color": "green"}, {"name": "B", "value": round(g["B"], 1), "color": "amber"},
		{"name": "Rejected", "value": round(g["Rejected"], 1), "color": "red"}], "format": "float", "unit": "m"},
		drilldown=report_route("Fabric Grade Analysis", ctx))


def defect_pareto(ctx) -> dict:
	rows = frappe.db.sql("""select ifnull(dt.defect_name, d.defect_type) defect, sum(d.points) pts from `tabFabric Roll Defect` d
		join `tabFabric Roll Inspection` p on p.name = d.parent left join `tabFabric Defect Type` dt on dt.name = d.defect_type
		where p.docstatus = 1 and p.company = %(company)s and p.inspection_date between %(from_date)s and %(to_date)s
		group by defect order by pts desc""", ctx)
	return widget("defect_pareto", "pareto", "Defects by Type (4-point system)", 4, Q.pareto([(r[0], flt(r[1])) for r in rows], "pts"),
		drilldown=report_route("Fabric Grade Analysis", ctx))


def qi_failures(ctx) -> dict:
	rows = frappe.db.sql("""select r.specification, ifnull(i.dm_stage, 'Other') stage, count(*) n from `tabQuality Inspection Reading` r
		join `tabQuality Inspection` qi on qi.name = r.parent join `tabItem` i on i.name = qi.item_code
		where qi.docstatus = 1 and r.status = 'Rejected' and qi.report_date between %(from_date)s and %(to_date)s
		group by r.specification, stage""", ctx, as_dict=True)
	params = sorted({r.specification for r in rows})
	stages = sorted({r.stage for r in rows})
	data = {(r.specification, r.stage): r.n for r in rows}
	return widget("qi_failures", "stacked_bar", "QI Failures by Parameter & Stage", 4,
		{"categories": params, "series": [{"name": s, "values": [data.get((p, s), 0) for p in params], "stack": "q"} for s in stages],
			"unit": ""}, drilldown=route("List", "Quality Inspection", status="Rejected"),
		note=None if rows else "No failed QI readings in the period.")


def shade_trend(ctx) -> dict:
	rows = frappe.db.sql("""select qi.report_date, i.dm_stage stage, avg(r.reading_1) de from `tabQuality Inspection Reading` r
		join `tabQuality Inspection` qi on qi.name = r.parent join `tabItem` i on i.name = qi.item_code
		where qi.docstatus = 1 and r.specification like 'Delta E%%' and i.dm_stage in %(stages)s
		and qi.report_date between %(start)s and %(end)s group by qi.report_date, stage order by qi.report_date""",
		{"stages": SHADE_STAGES, "start": add_days(ctx.to_date, -89), "end": ctx.to_date}, as_dict=True)
	dates = sorted({r.report_date for r in rows})
	data = defaultdict(dict)
	for r in rows:
		data[r.stage][r.report_date] = round(flt(r.de), 2)
	return widget("shade_trend", "line", "Shade Consistency — Delta E (tolerance 1.0)", 4,
		{"categories": [d.strftime("%d %b") for d in dates], "series": [{"name": s, "values": [data[s].get(d) for d in dates]} for s in SHADE_STAGES],
			"mark_line": 1.0, "unit": "ΔE", "points": True}, note=None if rows else "No Delta E readings in the last 90 days.")


def aging_buckets(ctx) -> dict:
	rows = Q.stock_by_age(ctx)
	groups = sorted({r.item_group or "Other" for r in rows})
	buckets = [b[1] for b in Q.AGE_BUCKETS]
	data = defaultdict(float)
	for r in rows:
		data[(r.item_group or "Other", r.bucket)] += flt(r.value)
	return widget("aging_buckets", "stacked_bar", "Stock Aging by Item Group (value)", 8,
		{"categories": groups, "series": [{"name": b, "values": [round(data[(g, b)], 0) for g in groups], "stack": "a"} for b in buckets],
			"format": "currency", "horizontal": True}, drilldown=route("query-report", "Stock Ageing"))
