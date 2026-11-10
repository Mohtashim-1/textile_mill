"""Queries shared by several dashboards (Part C §7)."""

from collections import defaultdict

import frappe
from frappe.utils import add_days, date_diff, flt, getdate

from textile_mill import reports_lib as rl
from textile_mill.constants import CONSUMABLE_ITEM_GROUPS, STAGE_WAREHOUSES
from textile_mill.dashboards import kpi as K

INVENTORY_CATEGORIES = {
	"Cotton Waste": "Raw Material",
	"Virgin Cotton": "Raw Material",
	"Chemicals & Dyes": "Chemicals & Dyes",
	"Trims": "Trims & Packing",
	"Packing Material": "Trims & Packing",
	"Fiber": "Intermediates",
	"Yarn": "Intermediates",
	"Fabric": "Intermediates",
	"Garment WIP": "Intermediates",
	"Finished Fabric": "Finished Goods",
	"Garments": "Finished Goods",
	"Waste": "Waste",
}
AGE_BUCKETS = ((30, "0–30 d"), (60, "31–60 d"), (90, "61–90 d"), (None, "90+ d"))


def warehouse(name: str, company: str) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	return f"{name} - {abbr}"


def rf(ctx, **extra) -> dict:
	return {"company": ctx.company, "from_date": ctx.from_date, "to_date": ctx.to_date, **extra}


def stage_buffer(ctx, stage: str) -> dict:
	"""Main-material quantity waiting in the stage's input store plus its WIP warehouse."""
	stores = STAGE_WAREHOUSES.get(stage)
	if not stores:
		return {"qty": 0, "value": 0, "uom": None}
	row = frappe.db.sql(
		"""select sum(b.actual_qty), sum(b.stock_value), max(i.stock_uom) from `tabBin` b join `tabItem` i on i.name = b.item_code
		where b.warehouse in %(wh)s and i.item_group not in %(consumables)s and b.actual_qty > 0""",
		{"wh": (warehouse(stores[0], ctx.company), warehouse(stores[1], ctx.company)), "consumables": CONSUMABLE_ITEM_GROUPS},
	)[0]
	return {"qty": flt(row[0]), "value": flt(row[1]), "uom": row[2]}


def stage_capacity_per_day(stage: str) -> float:
	"""Bottleneck capacity: the weakest workstation type of the stage (rated output × planned hours)."""
	by_type = defaultdict(float)
	for w in K.stage_workstations((stage,)):
		by_type[w.workstation_type or w.name] += flt(w.dm_rated_output_per_hour) * flt(w.dm_planned_hours_per_day or 8)
	values = [v for v in by_type.values() if v]
	return min(values) if values else 0


def downtime_by_reason(ctx, stages=None) -> list[tuple[str, float]]:
	conditions = ["l.docstatus = 1", "l.posting_date between %(from_date)s and %(to_date)s"]
	if stages:
		conditions.append("l.stage in %(stages)s")
	rows = frappe.db.sql(
		f"""select ifnull(r.reason_name, l.reason) reason, sum(l.duration_min) / 60 hrs from `tabMachine Downtime Log` l
		left join `tabDowntime Reason` r on r.name = l.reason where {" and ".join(conditions)}
		group by reason""",  # noqa: S608
		{**ctx, "stages": tuple(stages or ("",))},
	)
	out = {r[0]: flt(r[1]) for r in rows}
	shift_stages = [s for s in (stages or K.SHIFT_STAGES) if s in K.SHIFT_STAGES]
	if shift_stages:
		logged = set(frappe.get_all("Machine Downtime Log", filters={"docstatus": 1, "stage": ["in", shift_stages],
			"posting_date": ["between", [ctx.from_date, ctx.to_date]]}, pluck="workstation"))
		looms = sum(flt(r.stop_minutes) for r in K.loom_rows(ctx, shift_stages) if r.loom not in logged) / 60
		if looms:
			out["Loom stops (shift log)"] = out.get("Loom stops (shift log)", 0) + looms
		if "Knitting" in shift_stages:
			knit = sum(r.stop_minutes for r in K.shift_rows(ctx, ("Knitting",)) if r.machine not in logged) / 60
			if knit:
				out["Knitting stops (shift log)"] = knit
	return sorted(out.items(), key=lambda x: -x[1])


def pareto(items: list[tuple[str, float]], unit: str = "h") -> dict:
	total = sum(v for _k, v in items) or 1
	cumulative, running = [], 0
	for _k, v in items:
		running += v
		cumulative.append(round(running / total * 100, 1))
	return {"categories": [k for k, _v in items], "values": [round(v, 2) for _k, v in items], "cumulative": cumulative, "unit": unit}


def inventory_by_category(ctx) -> list[tuple[str, float]]:
	rows = frappe.db.sql(
		"""select i.item_group, ifnull(w.dm_inventory_status, 'Usable') status, sum(b.stock_value) value
		from `tabBin` b join `tabItem` i on i.name = b.item_code join `tabWarehouse` w on w.name = b.warehouse
		where w.company = %(company)s and b.actual_qty > 0 group by i.item_group, status""",
		ctx,
		as_dict=True,
	)
	out = defaultdict(float)
	for r in rows:
		key = "Work in Progress" if r.status == "WIP" else INVENTORY_CATEGORIES.get(r.item_group, "Other")
		out[key] += flt(r.value)
	return sorted(out.items(), key=lambda x: -x[1])


def age_bucket(days: int) -> str:
	for limit, label in AGE_BUCKETS:
		if limit is None or days <= limit:
			return label
	return AGE_BUCKETS[-1][1]


def stock_by_age(ctx, statuses=("Usable", "QC Hold", "B-Grade", "Rejected", "WIP")) -> list[dict]:
	"""Batch balances with age in days and stage of the item."""
	rows = K.batch_balances(ctx, statuses)
	for r in rows:
		r.age = date_diff(ctx.to_date, r.manufacturing_date or r.created)
		r.bucket = age_bucket(r.age)
		r.stage = frappe.get_cached_value("Item", r.item_code, "dm_stage")
		r.item_group = frappe.get_cached_value("Item", r.item_code, "item_group")
	return rows


def sales_by(ctx, key: str) -> dict[str, dict]:
	"""Revenue (Sales Invoice) and COGS (Delivery Note stock value) grouped by customer or item_code."""
	column = "si.customer" if key == "customer" else "sii.item_code"
	out = defaultdict(lambda: frappe._dict(revenue=0, cogs=0, qty=0))
	for r in frappe.db.sql(
		f"""select {column} k, sum(sii.base_net_amount) revenue, sum(sii.stock_qty) qty from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent where si.docstatus = 1 and si.company = %(company)s
		and si.posting_date between %(from_date)s and %(to_date)s group by k""",  # noqa: S608
		ctx,
		as_dict=True,
	):
		out[r.k].revenue += flt(r.revenue)
		out[r.k].qty += flt(r.qty)
	column = "dn.customer" if key == "customer" else "sle.item_code"
	for r in frappe.db.sql(
		f"""select {column} k, -sum(sle.stock_value_difference) cogs from `tabStock Ledger Entry` sle
		join `tabDelivery Note` dn on dn.name = sle.voucher_no where sle.voucher_type = 'Delivery Note' and sle.is_cancelled = 0
		and dn.company = %(company)s and sle.posting_date between %(from_date)s and %(to_date)s group by k""",  # noqa: S608
		ctx,
		as_dict=True,
	):
		out[r.k].cogs += flt(r.cogs)
	for v in out.values():
		v.margin = v.revenue - v.cogs
		v.margin_pct = v.margin / v.revenue * 100 if v.revenue else None
	return out


def daily_flow(ctx, stages, days: int = 30) -> tuple[list[str], list, list, list]:
	end = getdate(ctx.to_date)
	start = add_days(end, -(days - 1))
	inputs, outputs = defaultdict(float), defaultdict(float)
	for r in rl.manufacture_entries({"company": ctx.company, "from_date": start, "to_date": end}):
		if r.dm_stage in stages:
			inputs[getdate(r.posting_date)] += flt(r.input_qty)
			outputs[getdate(r.posting_date)] += flt(r.output_qty)
	labels, ins, outs, ylds = [], [], [], []
	for i in range(days):
		d = add_days(start, i)
		labels.append(d.strftime("%d %b"))
		ins.append(round(inputs[d], 2) if d in inputs else None)
		outs.append(round(outputs[d], 2) if d in outputs else None)
		ylds.append(round(outputs[d] / inputs[d] * 100, 1) if inputs.get(d) else None)
	return labels, ins, outs, ylds


def recent_qi(ctx, stages=None, limit: int = 20) -> list[dict]:
	conditions = ["qi.docstatus = 1", "qi.report_date between %(from_date)s and %(to_date)s"]
	if stages:
		conditions.append("i.dm_stage in %(stages)s")
	rows = frappe.db.sql(
		f"""select qi.name, qi.report_date, qi.item_code, qi.batch_no, qi.status, qi.inspection_type, qi.reference_name,
			(select group_concat(r.specification separator ', ') from `tabQuality Inspection Reading` r
				where r.parent = qi.name and r.status = 'Rejected') failed
		from `tabQuality Inspection` qi join `tabItem` i on i.name = qi.item_code where {" and ".join(conditions)}
		order by qi.report_date desc, qi.creation desc limit {int(limit)}""",  # noqa: S608
		{**ctx, "stages": tuple(stages or ("",))},
		as_dict=True,
	)
	return rows


def utilisation_heatmap(ctx, stages, days: int = 14) -> dict:
	"""Workstation × day utilisation % (run minutes ÷ planned minutes)."""
	end = getdate(ctx.to_date)
	start = add_days(end, -(days - 1))
	workstations = K.stage_workstations(stages)
	planned = {w.name: flt(w.dm_planned_hours_per_day or 8) * 60 for w in workstations}
	cells = defaultdict(float)
	for r in frappe.db.sql(
		"""select jc.workstation, date(tl.from_time) d, sum(tl.time_in_mins) m from `tabJob Card Time Log` tl
		join `tabJob Card` jc on jc.name = tl.parent where jc.docstatus = 1 and jc.company = %(company)s
		and date(tl.from_time) between %(start)s and %(end)s group by jc.workstation, d""",
		{"company": ctx.company, "start": start, "end": end},
		as_dict=True,
	):
		cells[(r.workstation, getdate(r.d))] += flt(r.m)
	for r in rl.loom_efficiency({"company": ctx.company, "from_date": start, "to_date": end}):
		cells[(r.loom, getdate(r.posting_date))] += 480 - flt(r.stop_minutes)
	active = sorted({w for (w, _d) in cells if w in planned}) or sorted(planned)[:20]
	x = [add_days(start, i) for i in range(days)]
	data = []
	for yi, w in enumerate(active):
		for xi, d in enumerate(x):
			if (w, d) in cells:
				data.append([xi, yi, round(min(cells[(w, d)] / planned[w] * 100, 150), 0)])
	return {"x": [d.strftime("%d %b") for d in x], "y": active, "data": data, "min": 0, "max": 100, "unit": "%"}
