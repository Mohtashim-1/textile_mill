"""KPI calculators (Part C §6). Each takes a parsed filter context and returns
{"value", "numerator", "denominator"}; value is None when there is no data."""

from collections import defaultdict

import frappe
from frappe.utils import add_days, date_diff, flt, getdate

from textile_mill import reports_lib as rl
from textile_mill import reports_lib_ht as ht
from textile_mill import reports_lib_knit as kn
from textile_mill.constants import DENIM_STAGES, HOME_TEXTILE_STAGES, KNIT_STAGES

DYEING_STAGES = ("Fiber Dyeing", "Indigo Dyeing", "Processing", "Knit Dyeing")
FINAL_FABRIC_STAGES = ("Finishing",)
GARMENT_STAGES = ("Garments", "Knit Garments")
# Loom stages report through Loom Shift Production (loom_type), not job cards.
LOOM_STAGES = {"Weaving": "Air-jet Denim", "Terry Weaving": "Terry", "Flat Weaving": "Flat Wide"}
# Stages whose machines report through shift sheets (Loom / Knitting Shift Production) instead of job cards.
SHIFT_STAGES = (*LOOM_STAGES, "Knitting")


def result(value=None, numerator=None, denominator=None) -> dict:
	return {"value": value, "numerator": numerator, "denominator": denominator}


def ratio(numerator, denominator, scale: float = 100) -> dict:
	numerator, denominator = flt(numerator), flt(denominator)
	return result(numerator / denominator * scale if denominator else None, numerator, denominator)


def _rf(ctx, **extra) -> dict:
	return {"company": ctx.company, "from_date": ctx.from_date, "to_date": ctx.to_date, **extra}


def _sql_value(query: str, values: dict) -> float:
	return flt((frappe.db.sql(query, values) or [[0]])[0][0])


def _plant_clause(ctx, alias: str, doctype: str) -> str:
	if ctx.get("plant") and frappe.get_meta(doctype).has_field("plant"):
		return f" and {alias}.plant = %(plant)s"
	return ""


# ---------------------------------------------------------------- commercial / finance
def revenue(ctx) -> dict:
	clause = _plant_clause(ctx, "si", "Sales Invoice") + (" and si.customer = %(customer)s" if ctx.get("customer") else "")
	return result(_sql_value(
		f"""select sum(si.base_net_total) from `tabSales Invoice` si where si.docstatus = 1 and si.company = %(company)s
		and si.posting_date between %(from_date)s and %(to_date)s {clause}""", ctx))


def cogs(ctx) -> dict:
	return result(_sql_value(
		"""select sum(gle.debit - gle.credit) from `tabGL Entry` gle join `tabAccount` acc on acc.name = gle.account
		where gle.is_cancelled = 0 and gle.company = %(company)s and acc.account_type = 'Cost of Goods Sold'
		and gle.posting_date between %(from_date)s and %(to_date)s""", ctx))


def gross_margin_pct(ctx) -> dict:
	rev = revenue(ctx)["value"]
	return ratio(flt(rev) - flt(cogs(ctx)["value"]), rev)


def production_value(ctx) -> dict:
	graded = _sql_value(
		"""select sum(sle.stock_value_difference) from `tabStock Ledger Entry` sle join `tabStock Entry` se on se.name = sle.voucher_no
		where sle.voucher_type = 'Stock Entry' and sle.is_cancelled = 0 and sle.actual_qty > 0 and se.purpose = 'Repack'
		and ifnull(se.fabric_roll_inspection, '') != '' and se.company = %(company)s and se.posting_date between %(from_date)s and %(to_date)s""",
		ctx,
	)
	garments = sum(flt(r.output_value) for r in rl.manufacture_entries(_rf(ctx)) if r.dm_stage in GARMENT_STAGES + ("Set Assembly",))
	return result(graded + garments)


def _stage_output(ctx, stages) -> float:
	return sum(flt(r.output_qty) for r in rl.manufacture_entries(_rf(ctx)) if r.dm_stage in stages)


def finished_fabric_m(ctx) -> dict:
	return result(_stage_output(ctx, FINAL_FABRIC_STAGES))


def garments_pcs(ctx) -> dict:
	return result(_stage_output(ctx, GARMENT_STAGES))


def order_book(ctx) -> dict:
	clause = " and so.customer = %(customer)s" if ctx.get("customer") else ""
	return result(_sql_value(
		f"""select sum((soi.stock_qty - soi.delivered_qty) * soi.base_rate / ifnull(nullif(soi.conversion_factor, 0), 1))
		from `tabSales Order Item` soi join `tabSales Order` so on so.name = soi.parent
		where so.docstatus = 1 and so.company = %(company)s and so.status not in ('Closed', 'Completed', 'On Hold')
		and soi.stock_qty > soi.delivered_qty {clause}""", ctx))


def otd_pct(ctx) -> dict:
	row = frappe.db.sql(
		"""select count(*), sum(dn.posting_date <= soi.delivery_date) from `tabDelivery Note Item` dni
		join `tabDelivery Note` dn on dn.name = dni.parent join `tabSales Order Item` soi on soi.name = dni.so_detail
		where dn.docstatus = 1 and dn.is_return = 0 and dn.company = %(company)s and dn.posting_date between %(from_date)s and %(to_date)s""",
		ctx,
	)[0]
	return ratio(row[1], row[0])


def booked(ctx) -> dict:
	return result(_sql_value(
		"""select sum(base_net_total) from `tabSales Order` where docstatus = 1 and company = %(company)s
		and transaction_date between %(from_date)s and %(to_date)s""", ctx))


def delivered(ctx) -> dict:
	return result(_sql_value(
		"""select sum(base_net_total) from `tabDelivery Note` where docstatus = 1 and is_return = 0 and company = %(company)s
		and posting_date between %(from_date)s and %(to_date)s""", ctx))


def ar_overdue(ctx) -> dict:
	return result(_sql_value(
		"""select sum(outstanding_amount) from `tabSales Invoice` where docstatus = 1 and company = %(company)s
		and outstanding_amount > 0 and due_date < %(to_date)s""", ctx))


def ap_due_30(ctx) -> dict:
	return result(_sql_value(
		"""select sum(outstanding_amount) from `tabPurchase Invoice` where docstatus = 1 and company = %(company)s
		and outstanding_amount > 0 and due_date <= date_add(%(to_date)s, interval 30 day)""", ctx))


def cash_position(ctx) -> dict:
	return result(_sql_value(
		"""select sum(gle.debit - gle.credit) from `tabGL Entry` gle join `tabAccount` acc on acc.name = gle.account
		where gle.is_cancelled = 0 and gle.company = %(company)s and acc.account_type in ('Bank', 'Cash')
		and gle.posting_date <= %(to_date)s""", ctx))


def utility_variance(ctx) -> dict:
	absorbed = sum(rl.absorbed_utilities(ctx.company, ctx.from_date, ctx.to_date).values())
	actual = sum(rl.actual_utilities(ctx.company, ctx.from_date, ctx.to_date).values())
	return result(absorbed - actual if (absorbed or actual) else None, absorbed, actual)


def std_cost_variance_amount(ctx) -> dict:
	rows = rl.cost_per_unit(_rf(ctx))
	return result(sum((r.actual_per_unit - r.standard_per_unit) * flt(r.output_qty) for r in rows) if rows else None)


# ---------------------------------------------------------------- inventory
def inventory_by_status(ctx, with_qty: bool = False) -> dict:
	"""Stock value (and qty) per warehouse inventory status as of ctx.to_date."""
	rows = frappe.db.sql(
		"""select ifnull(w.dm_inventory_status, 'Usable') status, sum(sle.stock_value_difference) value, sum(sle.actual_qty) qty
		from `tabStock Ledger Entry` sle join `tabWarehouse` w on w.name = sle.warehouse
		where sle.is_cancelled = 0 and sle.company = %(company)s and sle.posting_date <= %(to_date)s group by status""",
		ctx,
		as_dict=True,
	)
	if with_qty:
		return {r.status: {"value": flt(r.value), "qty": flt(r.qty)} for r in rows}
	return {r.status: flt(r.value) for r in rows}


def inventory_value(ctx) -> dict:
	return result(sum(inventory_by_status(ctx).values()))


def wip_value(ctx) -> dict:
	return result(inventory_by_status(ctx).get("WIP", 0))


def active_items_with_stock(ctx) -> dict:
	return result(_sql_value(
		"""select count(distinct b.item_code) from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
		where w.company = %(company)s and b.actual_qty > 0""", ctx))


def low_stock_rows(ctx) -> list[dict]:
	return frappe.db.sql(
		"""select r.parent item_code, i.item_name, i.item_group, r.warehouse, ifnull(b.actual_qty, 0) actual_qty,
			r.warehouse_reorder_level, r.warehouse_reorder_qty
		from `tabItem Reorder` r join `tabItem` i on i.name = r.parent
		join `tabWarehouse` w on w.name = r.warehouse
		left join `tabBin` b on b.item_code = r.parent and b.warehouse = r.warehouse
		where w.company = %(company)s and i.disabled = 0 and ifnull(b.actual_qty, 0) < r.warehouse_reorder_level""",
		ctx,
		as_dict=True,
	)


def low_stock_count(ctx) -> dict:
	return result(len(low_stock_rows(ctx)))


def batch_balances(ctx, statuses=("Usable",)) -> list[dict]:
	return frappe.db.sql(
		"""select e.batch_no, b.item_code, e.warehouse, sum(e.qty) qty, sum(e.stock_value_difference) value,
			bt.manufacturing_date, bt.expiry_date, date(bt.creation) created
		from `tabSerial and Batch Entry` e join `tabSerial and Batch Bundle` b on b.name = e.parent
		join `tabBatch` bt on bt.name = e.batch_no join `tabWarehouse` w on w.name = e.warehouse
		where b.docstatus = 1 and b.is_cancelled = 0 and w.company = %(company)s and b.posting_date <= %(to_date)s
		and ifnull(w.dm_inventory_status, 'Usable') in %(statuses)s
		group by e.batch_no, e.warehouse having sum(e.qty) > 0.0001""",
		{**ctx, "statuses": tuple(statuses)},
		as_dict=True,
	)


def aged_stock_value(ctx, days: int = 90) -> dict:
	cutoff = add_days(ctx.to_date, -days)
	return result(sum(flt(b.value) for b in batch_balances(ctx) if getdate(b.manufacturing_date or b.created) < getdate(cutoff)))


def inventory_accuracy(ctx) -> dict:
	row = frappe.db.sql(
		"""select sum(abs(i.qty - i.current_qty)), sum(i.qty) from `tabStock Reconciliation Item` i
		join `tabStock Reconciliation` sr on sr.name = i.parent where sr.docstatus = 1 and sr.company = %(company)s
		and sr.purpose = 'Stock Reconciliation' and sr.posting_date between %(from_date)s and %(to_date)s""",
		ctx,
	)[0]
	if not flt(row[1]):
		return result(None)
	return result((1 - flt(row[0]) / flt(row[1])) * 100, flt(row[1]) - flt(row[0]), flt(row[1]))


def wip_aging_days(ctx) -> dict:
	rows = batch_balances(ctx, ("WIP",))
	value = sum(flt(r.value) for r in rows)
	weighted = sum(flt(r.value) * date_diff(ctx.to_date, r.manufacturing_date or r.created) for r in rows)
	return ratio(weighted, value, 1)


def days_of_cover(ctx, item_code: str) -> float | None:
	on_hand = _sql_value("select sum(actual_qty) from `tabBin` where item_code = %(item)s", {"item": item_code})
	consumed = -_sql_value(
		"""select sum(actual_qty) from `tabStock Ledger Entry` where item_code = %(item)s and is_cancelled = 0
		and actual_qty < 0 and voucher_type = 'Stock Entry' and posting_date between %(from)s and %(to)s""",
		{"item": item_code, "from": add_days(ctx.to_date, -29), "to": ctx.to_date},
	)
	daily = consumed / 30
	return on_hand / daily if daily else None


# ---------------------------------------------------------------- production
def stage_yield(ctx, stage: str | None = None) -> dict:
	stage = stage or ctx.get("stage")
	row = next((r for r in rl.stage_yield_summary(_rf(ctx)) if r.stage == stage), None)
	if not row:
		return result(None)
	if row.yield_pct is None:
		return result(row.output_per_input, row.output_qty, row.input_qty)
	return result(row.yield_pct, row.output_qty, row.input_qty)


def recovery_yield(ctx) -> dict:
	return stage_yield(ctx, "Cotton Recycling")


def waste_pct(ctx, stage: str | None = None) -> dict:
	stage = stage or ctx.get("stage")
	row = next((r for r in rl.stage_yield_summary(_rf(ctx)) if r.stage == stage), None)
	return ratio(row.scrap_qty, row.input_qty) if row and row.same_uom else result(None)


def _wo_stage_clause(ctx, alias: str = "") -> str:
	return f" and {alias}dm_stage in %(stages)s" if ctx.get("stages") else ""


def plan_attainment(ctx) -> dict:
	row = frappe.db.sql(
		f"""select sum(produced_qty), sum(qty) from `tabWork Order` where docstatus = 1 and company = %(company)s
		and status != 'Stopped' and date(planned_start_date) between %(from_date)s and %(to_date)s{_wo_stage_clause(ctx)}""",  # noqa: S608
		{**ctx, "stages": tuple(ctx.get("stages") or ())},
	)[0]
	return ratio(row[0], row[1])


def open_work_orders(ctx) -> dict:
	row = frappe.db.sql(
		f"""select count(*), sum(ifnull(planned_end_date, expected_delivery_date) < now()) from `tabWork Order`
		where docstatus = 1 and company = %(company)s and status in ('Not Started', 'In Process'){_wo_stage_clause(ctx)}""",  # noqa: S608
		{**ctx, "stages": tuple(ctx.get("stages") or ())},
	)[0]
	return result(flt(row[0]), flt(row[1]), None)


def redye_pct(ctx) -> dict:
	row = frappe.db.sql(
		"""select count(*), sum(exists(select 1 from `tabJob Card` jc where jc.work_order = wo.name
			and jc.is_corrective_job_card = 1 and jc.docstatus = 1))
		from `tabWork Order` wo where wo.docstatus = 1 and wo.company = %(company)s and wo.dm_stage in %(stages)s
		and date(wo.planned_start_date) between %(from_date)s and %(to_date)s""",
		{**ctx, "stages": tuple(s for s in DYEING_STAGES if not ctx.get("stages") or s in ctx.get("stages")) or ("",)},
	)[0]
	return ratio(row[1], row[0])


def stage_workstations(stages) -> list[dict]:
	return frappe.get_all(
		"Workstation",
		filters={"dm_stage": ["in", list(stages)]},
		fields=["name", "dm_stage", "dm_rated_output_per_hour", "dm_planned_hours_per_day", "workstation_type"],
	)


def loom_rows(ctx, stages=None) -> list[dict]:
	"""Loom Shift rows for the loom stages among `stages` (all loom stages when None)."""
	types = {LOOM_STAGES[s] for s in (stages or LOOM_STAGES) if s in LOOM_STAGES}
	return [r for r in rl.loom_efficiency(_rf(ctx)) if (r.loom_type or "Air-jet Denim") in types]


def shift_rows(ctx, stages=None) -> list[dict]:
	"""Machine rows from shift sheets (looms and circular knitting): machine, output, stop minutes."""
	rows = [frappe._dict(machine=r.loom, output=flt(r.meters) or flt(r.kg), stop_minutes=flt(r.stop_minutes))
		for r in loom_rows(ctx, stages)]
	if stages is None or "Knitting" in stages:
		rows += [frappe._dict(machine=r.machine, output=flt(r.kg), stop_minutes=flt(r.stop_minutes))
			for r in kn.knitting_rows(_rf(ctx))]
	return rows


def downtime_minutes(ctx, stages=None, planned: int | None = 0) -> dict[str, float]:
	"""Unplanned downtime minutes per workstation (explicit logs + loom stops from shift logs)."""
	conditions = ["docstatus = 1", "posting_date between %(from_date)s and %(to_date)s"]
	if planned is not None:
		conditions.append(f"is_planned = {int(planned)}")
	if stages:
		conditions.append("stage in %(stages)s")
	out = defaultdict(float)
	for r in frappe.db.sql(
		f"select workstation, sum(duration_min) m from `tabMachine Downtime Log` where {' and '.join(conditions)} group by workstation",  # noqa: S608
		{**ctx, "stages": tuple(stages or ("",))},
		as_dict=True,
	):
		out[r.workstation] += flt(r.m)
	if planned in (0, None):
		logged = set(out)
		for r in shift_rows(ctx, stages):
			if r.machine not in logged:
				out[r.machine] += r.stop_minutes
	return out


def run_minutes(ctx, stages) -> dict[str, float]:
	"""Machine run minutes per workstation: job-card time logs; shift-sheet machines use shift hours minus stops."""
	out = defaultdict(float)
	for r in frappe.db.sql(
		"""select jc.workstation, sum(jc.total_time_in_mins) m from `tabJob Card` jc join `tabWork Order` wo on wo.name = jc.work_order
		where jc.docstatus = 1 and jc.is_corrective_job_card = 0 and wo.dm_stage in %(stages)s and wo.company = %(company)s
		and jc.posting_date between %(from_date)s and %(to_date)s and wo.dm_stage not in %(shift_stages)s
		group by jc.workstation""",
		{**ctx, "stages": tuple(stages), "shift_stages": SHIFT_STAGES},
		as_dict=True,
	):
		out[r.workstation] += flt(r.m)
	hours = 8 * 60
	for r in shift_rows(ctx, stages):
		out[r.machine] += hours - r.stop_minutes
	return out


def quality_rate(ctx, stages=None) -> dict:
	stages = stages or DENIM_STAGES
	parts = []
	if any(s in stages for s in ("Finishing", "Weaving")):
		g = rl.grade_split(_rf(ctx))
		if g["meters"]:
			parts.append((g["A"], g["meters"]))
	other = [s for s in stages if s not in ("Finishing", "Weaving")]
	if other:
		row = frappe.db.sql(
			"""select sum(if(exists(select 1 from `tabQuality Inspection` qi where qi.reference_name = se.name and qi.docstatus = 1
				and qi.status = 'Rejected') and not exists(select 1 from `tabQuality Inspection` qa where qa.reference_name = se.name
				and qa.docstatus = 1 and qa.status = 'Accepted'), 0, d.transfer_qty)), sum(d.transfer_qty)
			from `tabStock Entry` se join `tabStock Entry Detail` d on d.parent = se.name and d.is_finished_item = 1
			where se.docstatus = 1 and se.purpose = 'Manufacture' and se.company = %(company)s and se.dm_stage in %(stages)s
			and se.posting_date between %(from_date)s and %(to_date)s""",
			{**ctx, "stages": tuple(other)},
		)[0]
		if flt(row[1]):
			parts.append((flt(row[0]), flt(row[1])))
	if not parts:
		return result(None)
	# Average of stage ratios, so a large-volume stage does not hide a small one's rejects.
	return result(sum(g / t for g, t in parts) / len(parts) * 100)


def oee_parts(ctx, stages=None) -> dict:
	stages = tuple(stages or ctx.get("stages") or DENIM_STAGES)
	run = run_minutes(ctx, stages)
	down = downtime_minutes(ctx, stages)
	run_total, down_total = sum(run.values()), sum(down.values())
	if not run_total:
		return {"availability": None, "performance": None, "quality": None, "oee": None, "run_min": 0, "down_min": down_total}
	rated = {w.name: flt(w.dm_rated_output_per_hour) for w in stage_workstations(stages)}
	capacity = sum(run[w] / 60 * rated.get(w, 0) for w in run)
	output = _performance_output(ctx, stages, run)
	availability = run_total / (run_total + down_total)
	performance = min(output / capacity, 1) if capacity else None
	quality = quality_rate(ctx, stages)["value"]
	quality = quality / 100 if quality is not None else 1
	oee = availability * performance * quality if performance is not None else None
	return {
		"availability": availability * 100,
		"performance": performance * 100 if performance is not None else None,
		"quality": quality * 100,
		"oee": oee * 100 if oee is not None else None,
		"run_min": run_total,
		"down_min": down_total,
	}


def _performance_output(ctx, stages, run) -> float:
	"""Output measured in each workstation's rated UOM (sum over workstations that ran)."""
	woven = sum(r.output for r in shift_rows(ctx, stages))
	others = [s for s in stages if s not in SHIFT_STAGES]
	per_stage = {s: 0.0 for s in others}
	for r in rl.manufacture_entries(_rf(ctx)):
		if r.dm_stage in per_stage:
			per_stage[r.dm_stage] += flt(r.output_qty)
	# A unit passes every workstation of its route, so count it once per workstation type that ran.
	ws = {w.name: w for w in stage_workstations(stages)}
	ran_types = defaultdict(set)
	for w in run:
		if w in ws and ws[w].dm_stage in per_stage:
			ran_types[ws[w].dm_stage].add(w)
	total = woven
	for stage, workstations in ran_types.items():
		total += per_stage.get(stage, 0) * len(workstations)
	return total


def oee(ctx, stages=None) -> dict:
	return result(oee_parts(ctx, stages)["oee"])


def availability(ctx) -> dict:
	return result(oee_parts(ctx)["availability"])


def performance(ctx) -> dict:
	return result(oee_parts(ctx)["performance"])


def quality(ctx) -> dict:
	return result(oee_parts(ctx)["quality"])


def downtime_hrs(ctx) -> dict:
	return result(sum(downtime_minutes(ctx, ctx.get("stages")).values()) / 60)


def cost_per_unit(ctx, stage: str | None = None) -> dict:
	stage = stage or ctx.get("stage")
	row = next((r for r in rl.cost_per_unit_by_stage(_rf(ctx)) if r.stage == stage), None)
	return result(row.actual_per_unit, row.actual, row.output_qty) if row else result(None)


def std_variance_pct(ctx, stage: str | None = None) -> dict:
	stage = stage or ctx.get("stage")
	row = next((r for r in rl.cost_per_unit_by_stage(_rf(ctx)) if r.stage == stage), None)
	return result(row.variance_pct, row.actual_per_unit, row.standard_per_unit) if row else result(None)


def standard_cost_per_unit(ctx, stage: str | None = None) -> dict:
	stage = stage or ctx.get("stage")
	row = next((r for r in rl.cost_per_unit_by_stage(_rf(ctx)) if r.stage == stage), None)
	return result(row.standard_per_unit) if row else result(None)


def chem_variance_pct(ctx) -> dict:
	rows = [r for r in rl.recipe_variance(_rf(ctx)) if not r.get("is_total")]
	return ratio(sum(flt(r.actual_qty) - flt(r.standard_qty) for r in rows), sum(flt(r.standard_qty) for r in rows))


def a_grade_pct(ctx) -> dict:
	g = rl.grade_split(_rf(ctx))
	return ratio(g["A"], g["meters"])


def avg_defect_points(ctx) -> dict:
	rows = rl.fabric_grades(_rf(ctx))
	meters = sum(flt(r.meters) for r in rows)
	return ratio(sum(flt(r.avg_points) * flt(r.meters) for r in rows), meters, 1)


def first_pass_qi(ctx) -> dict:
	row = frappe.db.sql(
		"""select count(*), sum(first.status = 'Accepted') from (
			select qi.reference_name, substring_index(group_concat(qi.status order by qi.creation), ',', 1) status
			from `tabQuality Inspection` qi where qi.docstatus = 1 and qi.reference_type = 'Stock Entry'
			and qi.inspection_type = 'In Process' and qi.report_date between %(from_date)s and %(to_date)s
			group by qi.reference_name) first""",
		ctx,
	)[0]
	return ratio(row[1], row[0])


def loom_eff(ctx, loom_type: str = "Air-jet Denim") -> dict:
	filters = _rf(ctx, loom_type=loom_type)
	return result(rl.weighted_loom_efficiency(filters) if rl.loom_efficiency(filters) else None)


def terry_loom_eff(ctx) -> dict:
	return loom_eff(ctx, "Terry")


def cutting_var_pct(ctx) -> dict:
	row = frappe.db.sql(
		"""select sum(c.cutting_variance_m), sum(c.standard_fabric_m) from `tabCut Plan` c join `tabItem` i on i.name = c.style_template
		where c.docstatus = 1 and i.dm_stage = 'Garments' and c.company = %(company)s
		and c.posting_date between %(from_date)s and %(to_date)s""",
		ctx,
	)[0]
	return ratio(row[0], row[1])


# ---------------------------------------------------------------- procurement
def purchases(ctx) -> dict:
	return result(_sql_value(
		"""select sum(base_net_total) from `tabPurchase Receipt` where docstatus = 1 and is_return = 0 and company = %(company)s
		and posting_date between %(from_date)s and %(to_date)s""", ctx))


def open_po_value(ctx) -> dict:
	return result(_sql_value(
		"""select sum((poi.qty - poi.received_qty) * poi.base_rate) from `tabPurchase Order Item` poi
		join `tabPurchase Order` po on po.name = poi.parent where po.docstatus = 1 and po.company = %(company)s
		and po.status not in ('Closed', 'Completed') and poi.qty > poi.received_qty""", ctx))


def overdue_po_lines(ctx) -> dict:
	return result(_sql_value(
		"""select count(*) from `tabPurchase Order Item` poi join `tabPurchase Order` po on po.name = poi.parent
		where po.docstatus = 1 and po.company = %(company)s and po.status not in ('Closed', 'Completed')
		and poi.qty > poi.received_qty and poi.schedule_date < %(to_date)s""", ctx))


def avg_purchase_price(ctx, item_groups) -> dict:
	row = frappe.db.sql(
		"""select sum(pri.base_net_amount), sum(pri.stock_qty) from `tabPurchase Receipt Item` pri
		join `tabPurchase Receipt` pr on pr.name = pri.parent where pr.docstatus = 1 and pr.company = %(company)s
		and pr.posting_date between %(from_date)s and %(to_date)s and pri.item_group in %(groups)s""",
		{**ctx, "groups": tuple(item_groups)},
	)[0]
	return ratio(row[0], row[1], 1)


def cotton_waste_price(ctx) -> dict:
	return avg_purchase_price(ctx, ("Cotton Waste",))


def virgin_cotton_price(ctx) -> dict:
	return avg_purchase_price(ctx, ("Virgin Cotton",))


def supplier_qi_rejection(ctx) -> dict:
	row = frappe.db.sql(
		"""select count(*), sum(status = 'Rejected') from `tabQuality Inspection` where docstatus = 1
		and inspection_type = 'Incoming' and report_date between %(from_date)s and %(to_date)s""",
		ctx,
	)[0]
	return ratio(row[1], row[0])


# ---------------------------------------------------------------- sales
def orders_at_risk(ctx) -> list[dict]:
	"""Open SO lines where on-hand + WIP of the item (or its unwashed equivalent) is short of the pending qty."""
	rows = frappe.db.sql(
		"""select so.name sales_order, so.customer, soi.item_code, soi.delivery_date,
			soi.stock_qty - soi.delivered_qty required
		from `tabSales Order Item` soi join `tabSales Order` so on so.name = soi.parent
		where so.docstatus = 1 and so.company = %(company)s and so.status not in ('Closed', 'Completed', 'On Hold')
		and soi.stock_qty > soi.delivered_qty order by soi.delivery_date""",
		ctx,
		as_dict=True,
	)
	out = []
	for r in rows:
		available = _sql_value("select sum(actual_qty) from `tabBin` where item_code = %(i)s", {"i": r.item_code})
		wip = _sql_value(
			"""select sum(qty - produced_qty) from `tabWork Order` where docstatus = 1 and production_item = %(i)s
			and status in ('Not Started', 'In Process')""",
			{"i": r.item_code},
		)
		r.available = available + wip
		r.shortfall = max(flt(r.required) - r.available, 0)
		r.stage = frappe.get_cached_value("Item", r.item_code, "dm_stage")
		if r.shortfall > 0:
			out.append(r)
	return out


def orders_at_risk_count(ctx) -> dict:
	return result(len(orders_at_risk(ctx)))


def price_realisation(ctx, item_groups=("Finished Fabric",)) -> dict:
	row = frappe.db.sql(
		"""select sum(sii.base_net_amount), sum(sii.stock_qty) from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent where si.docstatus = 1 and si.company = %(company)s
		and si.posting_date between %(from_date)s and %(to_date)s and sii.item_group in %(groups)s""",
		{**ctx, "groups": tuple(item_groups)},
	)[0]
	return ratio(row[0], row[1], 1)


# ---------------------------------------------------------------- home textile (Part D §D9)
def ctp_yield(ctx) -> dict:
	t = ht.ctp_totals(_rf(ctx))
	return ratio(t["a"], t["planned"])


def seconds_pct(ctx) -> dict:
	t = ht.ctp_totals(_rf(ctx))
	return ratio(t["seconds"], t["cut"])


def weight_variance(ctx) -> dict:
	return result(ht.weight_variance_pct(_rf(ctx)))


def cotton_giveaway(ctx) -> dict:
	rows = ht.weight_checks(_rf(ctx))
	return result(sum(r.giveaway_kg for r in rows) if rows else None)


def set_completion(ctx) -> dict:
	return result(ht.set_completion_pct({"company": ctx.company}))


def cartons_shipped(ctx) -> dict:
	return result(ht.cartons_shipped(_rf(ctx)))


# ---------------------------------------------------------------- knitting (Part E §E8)
def knit_eff(ctx) -> dict:
	return result(kn.knit_efficiency(_rf(ctx)))


def knit_defects_per_roll(ctx) -> dict:
	return result(kn.defects_per_roll(_rf(ctx)))


def dye_machine_load(ctx) -> dict:
	return result(kn.dye_machine_load_pct(_rf(ctx)))


def knit_dye_loss(ctx) -> dict:
	y = stage_yield(ctx, "Knit Dyeing")
	return result(100 - y["value"], y["numerator"], y["denominator"]) if y["value"] is not None else y


def shrinkage_spirality_pass(ctx) -> dict:
	return result(kn.shrinkage_spirality_pass_pct(_rf(ctx)))


# ---------------------------------------------------------------- registry of calculators
CALCULATORS = {
	"REVENUE": revenue,
	"GROSS_MARGIN_PCT": gross_margin_pct,
	"PRODUCTION_VALUE": production_value,
	"FINISHED_FABRIC_M": finished_fabric_m,
	"GARMENTS_PCS": garments_pcs,
	"ORDER_BOOK": order_book,
	"OTD_PCT": otd_pct,
	"BOOKED": booked,
	"DELIVERED": delivered,
	"INVENTORY_VALUE": inventory_value,
	"WIP_VALUE": wip_value,
	"RECOVERY_YIELD": recovery_yield,
	"STAGE_YIELD": stage_yield,
	"WASTE_PCT": waste_pct,
	"PLAN_ATTAINMENT": plan_attainment,
	"AVAILABILITY": availability,
	"PERFORMANCE": performance,
	"QUALITY_RATE": quality,
	"OEE": oee,
	"DOWNTIME_HRS": downtime_hrs,
	"OPEN_WO": open_work_orders,
	"REDYE_PCT": redye_pct,
	"WIP_AGING_DAYS": wip_aging_days,
	"COST_PER_UNIT": cost_per_unit,
	"STD_VARIANCE_PCT": std_variance_pct,
	"STD_VARIANCE_AMOUNT": std_cost_variance_amount,
	"UTILITY_VARIANCE": utility_variance,
	"CHEM_VARIANCE_PCT": chem_variance_pct,
	"A_GRADE_PCT": a_grade_pct,
	"AVG_DEFECT_POINTS": avg_defect_points,
	"FIRST_PASS_QI": first_pass_qi,
	"LOOM_EFF": loom_eff,
	"CUTTING_VAR_PCT": cutting_var_pct,
	"ACTIVE_ITEMS": active_items_with_stock,
	"LOW_STOCK_COUNT": low_stock_count,
	"AGED_STOCK_VALUE": aged_stock_value,
	"INVENTORY_ACCURACY": inventory_accuracy,
	"AR_OVERDUE": ar_overdue,
	"AP_DUE_30": ap_due_30,
	"CASH_POSITION": cash_position,
	"PURCHASES": purchases,
	"OPEN_PO_VALUE": open_po_value,
	"OVERDUE_PO_LINES": overdue_po_lines,
	"COTTON_WASTE_PRICE": cotton_waste_price,
	"VIRGIN_COTTON_PRICE": virgin_cotton_price,
	"SUPPLIER_QI_REJECTION": supplier_qi_rejection,
	"ORDERS_AT_RISK": orders_at_risk_count,
	"PRICE_REALISATION_FABRIC": price_realisation,
	"CTP_YIELD": ctp_yield,
	"SECONDS_PCT": seconds_pct,
	"WEIGHT_VARIANCE_PCT": weight_variance,
	"COTTON_GIVEAWAY_KG": cotton_giveaway,
	"SET_COMPLETION_PCT": set_completion,
	"CARTONS_SHIPPED": cartons_shipped,
	"TERRY_LOOM_EFF": terry_loom_eff,
	"KNIT_EFF": knit_eff,
	"KNIT_DEFECTS_PER_ROLL": knit_defects_per_roll,
	"DYE_MACHINE_LOAD_PCT": dye_machine_load,
	"KNIT_DYE_LOSS_PCT": knit_dye_loss,
	"SHRINKAGE_SPIRALITY_PASS_PCT": shrinkage_spirality_pass,
}
STAGE_KPIS = {"STAGE_YIELD", "WASTE_PCT", "COST_PER_UNIT", "STD_VARIANCE_PCT"}


def calculate(code: str, ctx, stage: str | None = None) -> dict:
	fn = CALCULATORS[code]
	if code in STAGE_KPIS:
		return fn(ctx, stage or ctx.get("stage"))
	if code == "OEE" and stage:
		return fn(ctx, (stage,))
	return fn(ctx)


# ---------------------------------------------------------------- daily snapshots (Part C §5.3)
SNAPSHOT_KPIS = [
	("REVENUE", None), ("GROSS_MARGIN_PCT", None), ("PRODUCTION_VALUE", None), ("INVENTORY_VALUE", None),
	("WIP_VALUE", None), ("CASH_POSITION", None), ("ORDER_BOOK", None), ("OTD_PCT", None), ("OEE", None),
	("A_GRADE_PCT", None), ("LOOM_EFF", None), ("REDYE_PCT", None), ("FIRST_PASS_QI", None), ("DOWNTIME_HRS", None),
	("BOOKED", None), ("DELIVERED", None), ("PURCHASES", None), ("COTTON_WASTE_PRICE", None),
	("VIRGIN_COTTON_PRICE", None), ("PRICE_REALISATION_FABRIC", None),
	("CTP_YIELD", None), ("SECONDS_PCT", None), ("TERRY_LOOM_EFF", None), ("CARTONS_SHIPPED", None),
	("KNIT_EFF", None), ("DYE_MACHINE_LOAD_PCT", None), ("KNIT_DYE_LOSS_PCT", None),
] + [(code, s) for s in DENIM_STAGES + HOME_TEXTILE_STAGES + KNIT_STAGES for code in ("STAGE_YIELD", "COST_PER_UNIT", "OEE")]


def snapshot_all(date, company: str | None = None) -> int:
	"""Upsert real (non-synthetic) daily snapshots for one day. Returns rows written."""
	date = getdate(date)
	company = company or frappe.db.get_single_value("Global Defaults", "default_company")
	ctx = frappe._dict(company=company, from_date=date, to_date=date, stages=None, stage=None, plant=None)
	written = 0
	for code, stage in SNAPSHOT_KPIS:
		if not frappe.db.exists("KPI Definition", code):
			continue
		res = calculate(code, frappe._dict(ctx, stage=stage), stage)
		if res["value"] is None:
			continue
		name = frappe.db.get_value("KPI Daily Snapshot", {"snapshot_date": date, "kpi": code, "stage": stage or "", "plant": ["is", "not set"]})
		values = {"value": flt(res["value"], 4), "numerator": flt(res.get("numerator")), "denominator": flt(res.get("denominator")), "is_synthetic": 0}
		if name:
			frappe.db.set_value("KPI Daily Snapshot", name, values, update_modified=False)
		else:
			frappe.get_doc({"doctype": "KPI Daily Snapshot", "snapshot_date": date, "kpi": code, "stage": stage or "", **values}).insert(
				ignore_permissions=True
			)
		written += 1
	return written
