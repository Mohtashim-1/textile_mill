"""D6 Procurement & Suppliers (CFO, Purchase Manager)."""

from collections import defaultdict

import frappe
from frappe.utils import add_months, flt, get_first_day, getdate

from textile_mill import reports_lib as rl
from textile_mill.dashboards import kpi as K
from textile_mill.dashboards import queries as Q
from textile_mill.dashboards.common import run_widgets, monthly_trend, route, table, tile, widget

PRICE_SERIES = (
	("Cotton waste", ("CW-PRE", "CW-POST"), "COTTON_WASTE_PRICE"),
	("Virgin cotton", ("VC-RAW",), "VIRGIN_COTTON_PRICE"),
	("Indigo dye", ("CHM-IND",), None),
	("Hydrosulphite", ("CHM-HYD",), None),
)
CRITICAL_ITEMS = ("CW-PRE", "VC-RAW", "CHM-IND", "CHM-HYD", "CHM-CAU", "CHM-SIZE", "CHM-SBLK", "TRM-ZIP", "TRM-THR")
MIN_COVER_DAYS = 15
RECOVERY_TARGET = 85.0


def build(ctx) -> tuple[list, list]:
	tiles = [
		tile(ctx, "PURCHASES", label="Purchases (period)", drilldown=route("List", "Purchase Receipt")),
		tile(ctx, "OPEN_PO_VALUE", label="Open PO Value", compare=False, drilldown=route("List", "Purchase Order", status=["not in", ["Closed", "Completed"]])),
		tile(ctx, "OVERDUE_PO_LINES", label="Overdue PO Lines", compare=False, drilldown=route("List", "Purchase Order")),
		tile(ctx, "COTTON_WASTE_PRICE", label="Cotton Waste PKR/kg"),
		tile(ctx, "VIRGIN_COTTON_PRICE", label="Virgin Cotton PKR/kg"),
		tile(ctx, "SUPPLIER_QI_REJECTION", label="Supplier QI Rejection %", drilldown=route("List", "Quality Inspection", inspection_type="Incoming")),
	]
	widgets = [
		lambda: price_trend(ctx),
		lambda: supplier_scorecard(ctx),
		lambda: days_of_cover(ctx),
		lambda: consumption_vs_purchase(ctx),
		lambda: pending_receipts(ctx),
	]
	return tiles, run_widgets(widgets)


def price_trend(ctx) -> dict:
	end = getdate(ctx.to_date)
	start = add_months(get_first_day(end), -11)
	months = [add_months(start, i).strftime("%Y-%m") for i in range(12)]
	out = []
	labels = [add_months(start, i).strftime("%b %y") for i in range(12)]
	for name, items, kpi in PRICE_SERIES:
		live = dict(frappe.db.sql(
			"""select date_format(pr.posting_date, '%%Y-%%m') m, sum(pri.base_net_amount) / sum(pri.stock_qty)
			from `tabPurchase Receipt Item` pri join `tabPurchase Receipt` pr on pr.name = pri.parent where pr.docstatus = 1
			and pr.company = %(company)s and pri.item_code in %(items)s and pr.posting_date between %(start)s and %(end)s group by m""",
			{"company": ctx.company, "items": items, "start": start, "end": end},
		))
		history = monthly_trend(ctx, kpi)[1] if kpi else [None] * 12
		out.append({"name": name, "values": [round(flt(live[m]), 1) if m in live else history[i] for i, m in enumerate(months)],
			"axis": 1 if name in ("Indigo dye", "Hydrosulphite") else 0})
	return widget("price_trend", "line", "Purchase Price Trend (PKR/kg)", 8,
		{"categories": labels, "series": out, "format": "currency", "dual_axis": True, "points": True},
		synthetic=bool(ctx.get("synthetic")), note="Chemicals on the right axis.")


def supplier_scorecard(ctx) -> dict:
	spend = {r.supplier: r for r in frappe.db.sql(
		"""select pr.supplier, sum(pri.base_net_amount) spend, count(*) n_lines,
			sum(pr.posting_date <= ifnull(poi.schedule_date, pr.posting_date)) on_time
		from `tabPurchase Receipt Item` pri join `tabPurchase Receipt` pr on pr.name = pri.parent
		left join `tabPurchase Order Item` poi on poi.name = pri.purchase_order_item
		where pr.docstatus = 1 and pr.is_return = 0 and pr.company = %(company)s and pr.posting_date between %(from_date)s and %(to_date)s
		group by pr.supplier""", ctx, as_dict=True)}
	qi = {r.supplier: r for r in frappe.db.sql(
		"""select pr.supplier, count(*) n, sum(qi.status = 'Rejected') rejected from `tabQuality Inspection` qi
		join `tabPurchase Receipt` pr on pr.name = qi.reference_name where qi.docstatus = 1 and qi.reference_type = 'Purchase Receipt'
		and qi.report_date between %(from_date)s and %(to_date)s group by pr.supplier""", ctx, as_dict=True)}
	recovery = _recovery_by_supplier(ctx)
	rows = []
	for supplier, s in sorted(spend.items(), key=lambda x: -flt(x[1].spend)):
		on_time = flt(s.on_time) / s.n_lines * 100 if s.n_lines else None
		rejection = flt(qi[supplier].rejected) / qi[supplier].n * 100 if supplier in qi and qi[supplier].n else 0
		rec = recovery.get(supplier)
		score = 0.4 * (on_time or 0) + 0.3 * (100 - rejection) + 0.3 * (min(rec / RECOVERY_TARGET * 100, 100) if rec else 100)
		rows.append({"supplier": supplier, "spend": s.spend, "on_time": on_time, "rejection": rejection, "recovery": rec, "score": score,
			"_status": {"score": "green" if score >= 90 else ("amber" if score >= 75 else "red")},
			"_route": {"supplier": ["Form", "Supplier", supplier]}})
	return widget("supplier_scorecard", "table", "Supplier Scorecard", 12, table(
		[("Supplier", "supplier", "link"), ("Spend", "spend", "currency"), ("On-time %", "on_time", "percent"),
			("QI Rejection %", "rejection", "percent"), ("Recovery Yield of their Waste %", "recovery", "percent"), ("Score", "score", "int")], rows),
		explain="Score = 40% on-time receipt + 30% QI pass rate + 30% recovery yield vs 85% target (cotton-waste suppliers only).")


def _recovery_by_supplier(ctx) -> dict[str, float]:
	"""Recovery yield attributed to the supplier of each consumed cotton-waste batch (output allocated pro rata to input)."""
	inputs, outputs = defaultdict(float), defaultdict(float)
	for se in rl.manufacture_entries(Q.rf(ctx, dm_stage="Cotton Recycling")):
		entries = frappe.db.sql(
			"""select e.batch_no, -e.qty qty from `tabSerial and Batch Entry` e join `tabSerial and Batch Bundle` b on b.name = e.parent
			where b.voucher_no = %s and b.type_of_transaction = 'Outward' and b.docstatus = 1 and b.is_cancelled = 0""",
			se.stock_entry,
			as_dict=True,
		)
		total = sum(flt(e.qty) for e in entries)
		for e in entries:
			supplier = frappe.db.get_value("Batch", e.batch_no, "supplier") or _receipt_supplier(e.batch_no)
			if supplier and total:
				inputs[supplier] += flt(e.qty)
				outputs[supplier] += flt(se.output_qty) * flt(e.qty) / total
	return {s: outputs[s] / inputs[s] * 100 for s in inputs if inputs[s]}


def _receipt_supplier(batch_no: str) -> str | None:
	row = frappe.db.sql(
		"""select pr.supplier from `tabSerial and Batch Bundle` b join `tabPurchase Receipt` pr on pr.name = b.voucher_no
		join `tabSerial and Batch Entry` e on e.parent = b.name where e.batch_no = %s and b.voucher_type = 'Purchase Receipt' limit 1""",
		batch_no,
	)
	return row[0][0] if row else None


def days_of_cover(ctx) -> dict:
	items, values = [], []
	for item in CRITICAL_ITEMS:
		if not frappe.db.exists("Item", item):
			continue
		cover = K.days_of_cover(ctx, item)
		items.append(item)
		values.append(round(cover, 1) if cover is not None else None)
	return widget("days_of_cover", "bar", f"Days of Cover — critical materials (min {MIN_COVER_DAYS} d)", 6,
		{"categories": items, "series": [{"name": "Days of cover", "values": values}], "mark_line": MIN_COVER_DAYS, "unit": "d",
			"threshold_low": MIN_COVER_DAYS}, explain="On hand ÷ average daily consumption over the last 30 days. Blank = not consumed.")


def consumption_vs_purchase(ctx) -> dict:
	consumed = dict(frappe.db.sql("""select sle.item_code, -sum(sle.actual_qty) from `tabStock Ledger Entry` sle join `tabItem` i on i.name = sle.item_code
		where sle.is_cancelled = 0 and sle.actual_qty < 0 and sle.voucher_type = 'Stock Entry' and i.item_group = 'Chemicals & Dyes'
		and sle.company = %(company)s and sle.posting_date between %(from_date)s and %(to_date)s group by sle.item_code""", ctx))
	bought = dict(frappe.db.sql("""select pri.item_code, sum(pri.stock_qty) from `tabPurchase Receipt Item` pri join `tabPurchase Receipt` pr
		on pr.name = pri.parent where pr.docstatus = 1 and pr.company = %(company)s and pri.item_group = 'Chemicals & Dyes'
		and pr.posting_date between %(from_date)s and %(to_date)s group by pri.item_code""", ctx))
	items = sorted(set(consumed) | set(bought), key=lambda i: -flt(consumed.get(i)))
	return widget("chem_consumption", "grouped_bar", "Chemicals: Consumed vs Purchased (kg)", 6,
		{"categories": items, "series": [{"name": "Consumed", "values": [round(flt(consumed.get(i)), 1) for i in items]},
			{"name": "Purchased", "values": [round(flt(bought.get(i)), 1) for i in items]}], "unit": "kg"},
		drilldown=route("query-report", "Recipe Consumption Variance"))


def pending_receipts(ctx) -> dict:
	rows = frappe.db.sql("""select po.name, po.supplier, poi.item_code, poi.qty - poi.received_qty pending, poi.schedule_date,
		(poi.qty - poi.received_qty) * poi.base_rate value from `tabPurchase Order Item` poi join `tabPurchase Order` po on po.name = poi.parent
		where po.docstatus = 1 and po.company = %(company)s and po.status not in ('Closed', 'Completed') and poi.qty > poi.received_qty
		order by poi.schedule_date limit 50""", ctx, as_dict=True)
	for r in rows:
		r._status = {"schedule_date": "red" if getdate(r.schedule_date) < getdate(ctx.to_date) else None}
		r._route = {"name": ["Form", "Purchase Order", r.name]}
	return widget("pending_receipts", "table", "Pending Receipts", 12, table(
		[("Purchase Order", "name", "link"), ("Supplier", "supplier"), ("Item", "item_code"), ("Pending", "pending", "float"),
			("Due", "schedule_date", "date"), ("Value", "value", "currency")], rows), note=None if rows else "No open purchase order lines.")
