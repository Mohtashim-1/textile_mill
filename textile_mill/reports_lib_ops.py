"""Operational control reports: exception (critical) reports and detail registers (docs/REPORTS.md §2–3).

Built on the same query helpers as the core reports and dashboards, so numbers agree across screens."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, today

from textile_mill import reports_lib as rl
from textile_mill import reports_lib_ht as ht
from textile_mill import reports_lib_knit as kn
from textile_mill.constants import BUSINESS_LINES, PRODUCTION_STAGES, WASTE_ITEM_GROUP
from textile_mill.dashboards import kpi
from textile_mill.dashboards.queries import age_bucket
from textile_mill.dashboards.targets import get_target, rag

DYE_HOUSE_STAGES = ("Fiber Dyeing", "Indigo Dyeing", "Processing", "Printing", "Knit Dyeing")
CHEMICAL_GROUP = "Chemicals & Dyes"
OPEN_WO_STATUSES = ("Not Started", "In Process")
CLOSED_SO_STATUSES = ("Closed", "Completed", "On Hold")


def _ctx(filters, **extra) -> frappe._dict:
	f, company, from_date, to_date = rl._period(filters)
	return frappe._dict(company=company, from_date=from_date, to_date=to_date, **extra)


def _employee_name(employee: str | None) -> str | None:
	return frappe.get_cached_value("Employee", employee, "employee_name") if employee else None


def _company_bins(company: str | None, item_codes, exclude_statuses=("WIP",)) -> dict[str, float]:
	if not item_codes:
		return {}
	rows = frappe.db.sql(
		f"""select b.item_code, sum(b.actual_qty) qty from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
		where b.item_code in %(items)s and ifnull(w.dm_inventory_status, 'Usable') not in %(excl)s
		{"and w.company = %(company)s" if company else ""} group by b.item_code""",  # noqa: S608
		{"items": tuple(item_codes), "excl": tuple(exclude_statuses) or ("",), "company": company},
	)
	return {i: flt(q) for i, q in rows}


def business_line(stage: str | None) -> str:
	"""Business line of an item stage; Spinning (shared) and raw items count as Denim, the original line."""
	for line, stages in BUSINESS_LINES.items():
		if stage in stages and stage != "Spinning":
			return line
	return "Denim"


# ================================================================ critical (exception) reports
def yield_exceptions(filters) -> list[dict]:
	"""Work orders whose yield is below the stage target, with the loss against target in qty and value."""
	f = frappe._dict(filters or {})
	out = []
	for r in rl.stage_yield({**f, "group_by_work_order": 1}):
		if r.yield_pct is None:
			continue
		target = get_target("STAGE_YIELD", r.dm_stage, on_date=r.posting_date)
		if not target:
			continue
		status = rag(r.yield_pct, target)
		if r.yield_pct >= flt(target.target_value) and not f.get("show_all"):
			continue
		unit_value = flt(r.output_value) / flt(r.output_qty) if flt(r.output_qty) else 0
		gap_qty = max(flt(r.input_qty) * (flt(target.target_value) - r.yield_pct) / 100, 0)
		out.append(frappe._dict(
			work_order=r.work_order, stock_entry=r.stock_entry, posting_date=r.posting_date, stage=r.dm_stage,
			item_code=r.output_item, uom=r.output_uom, input_qty=r.input_qty, output_qty=r.output_qty,
			yield_pct=r.yield_pct, target_pct=flt(target.target_value), gap_pct=flt(target.target_value) - r.yield_pct,
			loss_qty=gap_qty, loss_value=gap_qty * unit_value, status=status.title(),
		))
	return sorted(out, key=lambda r: -r.loss_value)


def late_order_risk(filters) -> list[dict]:
	"""Open Sales Order lines classified Overdue / At Risk / On Track from stock, open work orders and due date."""
	f = frappe._dict(filters or {})
	as_on = getdate(f.get("as_on_date") or today())
	rows = frappe.db.sql(
		f"""select so.name sales_order, so.customer, soi.item_code, soi.delivery_date, soi.stock_uom uom,
			soi.stock_qty ordered_qty, soi.delivered_qty * soi.conversion_factor delivered_qty,
			soi.stock_qty - soi.delivered_qty * soi.conversion_factor pending_qty,
			(soi.qty - soi.delivered_qty) * soi.base_net_rate pending_value
		from `tabSales Order Item` soi join `tabSales Order` so on so.name = soi.parent
		where so.docstatus = 1 and so.status not in %(closed)s and soi.stock_qty > soi.delivered_qty * soi.conversion_factor
		{"and so.company = %(company)s" if f.get("company") else ""}
		{"and so.customer = %(customer)s" if f.get("customer") else ""}
		order by soi.delivery_date""",  # noqa: S608
		{"closed": CLOSED_SO_STATUSES, "company": f.get("company"), "customer": f.get("customer")},
		as_dict=True,
	)
	stock = _company_bins(f.get("company"), {r.item_code for r in rows})
	for r in rows:
		r.in_stock = stock.get(r.item_code, 0)
		r.in_production = flt(frappe.db.sql(
			"""select sum(qty - produced_qty) from `tabWork Order` where docstatus = 1 and production_item = %s
			and status in %s""", (r.item_code, OPEN_WO_STATUSES))[0][0])
		r.shortfall = max(flt(r.pending_qty) - r.in_stock - r.in_production, 0)
		r.days_to_due = date_diff(r.delivery_date, as_on) if r.delivery_date else None
		r.stage = frappe.get_cached_value("Item", r.item_code, "dm_stage")
		r.business_line = business_line(r.stage)
		if r.days_to_due is not None and r.days_to_due < 0:
			r.status = "Overdue"
		elif r.shortfall > 0:
			r.status = "At Risk"
		else:
			r.status = "On Track"
	if f.get("only_exceptions"):
		rows = [r for r in rows if r.status != "On Track"]
	return rows


def material_shortage(filters) -> list[dict]:
	"""Material still to be issued to open work orders vs free stock and open purchase orders."""
	f = frappe._dict(filters or {})
	reqs = frappe.db.sql(
		f"""select woi.item_code, i.item_name, i.item_group, i.stock_uom uom,
			sum(greatest(woi.required_qty - greatest(woi.transferred_qty, woi.consumed_qty), 0)) required_qty,
			count(distinct wo.name) work_orders, min(date(wo.planned_start_date)) first_need
		from `tabWork Order Item` woi join `tabWork Order` wo on wo.name = woi.parent join `tabItem` i on i.name = woi.item_code
		where wo.docstatus = 1 and wo.status in %(open)s {"and wo.company = %(company)s" if f.get("company") else ""}
		group by woi.item_code having required_qty > 0""",  # noqa: S608
		{"open": OPEN_WO_STATUSES, "company": f.get("company")},
		as_dict=True,
	)
	items = {r.item_code for r in reqs}
	stock = _company_bins(f.get("company"), items, ("WIP", "Waste", "Rejected", "QC Hold"))
	on_order = dict(frappe.db.sql(
		f"""select poi.item_code, sum(poi.stock_qty - poi.received_qty * poi.conversion_factor)
		from `tabPurchase Order Item` poi join `tabPurchase Order` po on po.name = poi.parent
		where po.docstatus = 1 and po.status not in ('Closed', 'Completed') and poi.item_code in %(items)s
		{"and po.company = %(company)s" if f.get("company") else ""} group by poi.item_code""",  # noqa: S608
		{"items": tuple(items) or ("",), "company": f.get("company")},
	)) if items else {}
	out = []
	for r in reqs:
		r.in_stock = stock.get(r.item_code, 0)
		r.on_order = max(flt(on_order.get(r.item_code)), 0)
		r.short_now = max(flt(r.required_qty) - r.in_stock, 0)
		r.shortage = max(r.short_now - r.on_order, 0)
		r.status = "Short" if r.shortage > 0 else ("Covered by PO" if r.short_now > 0 else "Available")
		if f.get("only_exceptions") and r.status == "Available":
			continue
		out.append(r)
	return sorted(out, key=lambda r: (r.status == "Available", r.status == "Covered by PO", r.first_need or getdate("2100-01-01")))


def margin_erosion(filters) -> list[dict]:
	"""Work orders whose actual unit cost exceeds the BOM standard by at least `threshold_pct`."""
	f = frappe._dict(filters or {})
	threshold = flt(f.get("threshold_pct") if f.get("threshold_pct") is not None else 5)
	out = []
	for r in rl.cost_per_unit(f):
		if r.variance_pct is None or r.variance_pct < threshold:
			continue
		r.excess_cost = flt(r.variance_per_unit) * flt(r.output_qty)
		r.sales_order = frappe.db.get_value("Work Order", r.work_order, "sales_order") if r.work_order else None
		out.append(r)
	return sorted(out, key=lambda r: -r.excess_cost)


def aged_wip(filters) -> list[dict]:
	"""Batches sitting in WIP / QC Hold / B-Grade warehouses longer than `min_age_days`."""
	f = frappe._dict(filters or {})
	ctx = _ctx(f)
	statuses = tuple(s.strip() for s in (f.get("statuses") or "WIP,QC Hold,B-Grade").split(",") if s.strip())
	min_age = int(f.get("min_age_days") or 0)
	out = []
	for b in kpi.batch_balances(ctx, statuses):
		age = date_diff(ctx.to_date, b.manufacturing_date or b.created)
		if age < min_age:
			continue
		stage = frappe.get_cached_value("Item", b.item_code, "dm_stage")
		out.append(frappe._dict(
			batch_no=b.batch_no, item_code=b.item_code, stage=stage, warehouse=b.warehouse,
			inventory_status=frappe.get_cached_value("Warehouse", b.warehouse, "dm_inventory_status") or "Usable",
			qty=b.qty, uom=frappe.get_cached_value("Item", b.item_code, "stock_uom"), value=b.value, age_days=age,
			age_bucket=age_bucket(age),
		))
	return sorted(out, key=lambda r: -r.age_days)


def quality_hold(filters) -> list[dict]:
	"""Everything blocked by quality: draft manufacture entries awaiting QI, rejected inspections, QC-hold stock."""
	f = frappe._dict(filters or {})
	ctx = _ctx(f)
	as_on = ctx.to_date
	out = []
	for se in frappe.db.sql(
		f"""select se.name, se.posting_date, se.work_order, se.dm_stage,
			max(if(d.is_finished_item = 1, d.item_code, null)) item_code,
			sum(if(d.is_finished_item = 1, d.transfer_qty, 0)) qty, sum(if(d.is_finished_item = 1, d.amount, 0)) value
		from `tabStock Entry` se join `tabStock Entry Detail` d on d.parent = se.name
		where se.docstatus = 0 and se.purpose = 'Manufacture' {"and se.company = %(company)s" if ctx.company else ""}
		group by se.name""",  # noqa: S608
		ctx,
		as_dict=True,
	):
		out.append(frappe._dict(hold_type="Awaiting QI", reference_doctype="Stock Entry", reference_name=se.name,
			posting_date=se.posting_date, stage=se.dm_stage, item_code=se.item_code, qty=se.qty, value=se.value,
			age_days=date_diff(as_on, se.posting_date), remarks=_("Draft manufacture entry for {0}").format(se.work_order or "-")))
	for qi in frappe.db.sql(
		"""select name, report_date, item_code, batch_no, reference_type, reference_name, sample_size, remarks
		from `tabQuality Inspection` where docstatus = 1 and status = 'Rejected' and report_date between %(from_date)s and %(to_date)s""",
		ctx,
		as_dict=True,
	):
		out.append(frappe._dict(hold_type="Rejected QI", reference_doctype="Quality Inspection", reference_name=qi.name,
			posting_date=qi.report_date, stage=frappe.get_cached_value("Item", qi.item_code, "dm_stage"), item_code=qi.item_code,
			batch_no=qi.batch_no, age_days=date_diff(as_on, qi.report_date),
			remarks=f"{qi.reference_type or ''} {qi.reference_name or ''}".strip() or qi.remarks))
	for b in kpi.batch_balances(ctx, ("QC Hold", "Rejected")):
		out.append(frappe._dict(hold_type="Held Stock", reference_doctype="Batch", reference_name=b.batch_no,
			posting_date=b.manufacturing_date or b.created, stage=frappe.get_cached_value("Item", b.item_code, "dm_stage"),
			item_code=b.item_code, batch_no=b.batch_no, qty=b.qty, value=b.value,
			age_days=date_diff(as_on, b.manufacturing_date or b.created), remarks=b.warehouse))
	return out


def corrective_cost_summary(filters) -> list[dict]:
	"""Re-dye / re-process jobs grouped by stage, workstation and operation, with cost and re-dye rate."""
	f = frappe._dict(filters or {})
	rates = rl.redye_pct_by_stage(f)
	groups: dict[tuple, dict] = {}
	for j in rl.corrective_jobs(f):
		key = (j.dm_stage, j.workstation, j.operation)
		g = groups.setdefault(key, frappe._dict(stage=j.dm_stage, workstation=j.workstation, operation=j.operation,
			jobs=0, work_orders=set(), hours=0, cost=0, reasons=set()))
		g.jobs += 1
		g.work_orders.add(j.work_order)
		g.hours += flt(j.hours)
		g.cost += flt(j.cost)
		if j.reason:
			g.reasons.add(j.reason)
	out = []
	for g in groups.values():
		g.work_orders = len(g.work_orders)
		g.reasons = "; ".join(sorted(g.reasons))[:200]
		g.redye_pct = rates.get(g.stage)
		out.append(g)
	return sorted(out, key=lambda r: -r.cost)


def recall_trace(filters) -> list[dict]:
	"""Every customer shipment that contains material from a given batch (forward genealogy)."""
	f = frappe._dict(filters or {})
	if not f.get("batch_no"):
		frappe.throw(_("Select the Batch (lot) to trace."))
	rows = rl.genealogy({"batch_no": f.batch_no, "direction": "Forward", "max_depth": f.get("max_depth") or 15})
	by_name = {r.name: r for r in rows}

	def via(node) -> str:
		parent = by_name.get(node.parent_node)
		return parent.batch_no or parent.voucher_no if parent else None

	out, seen = [], set()
	for r in rows:
		if r.node_type == "Customer":
			key = (r.voucher_type, r.voucher_no)
			if key in seen:
				continue
			seen.add(key)
			parent = by_name.get(r.parent_node) or frappe._dict()
			out.append(frappe._dict(customer=r.party, voucher_type=r.voucher_type, voucher_no=r.voucher_no,
				posting_date=r.posting_date, item_code=parent.item_code, batch_no=parent.batch_no, qty=r.qty,
				uom=parent.uom, depth=r.indent, via=via(r)))
		elif r.node_type == "Work Order":
			sales_order = frappe.db.get_value("Work Order", r.voucher_no, "sales_order")
			if not sales_order:
				cut_plan = frappe.db.get_value("Cut Plan Size", {"work_order": r.voucher_no}, "parent")
				sales_order = frappe.db.get_value("Cut Plan", cut_plan, "sales_order") if cut_plan else None
			if not sales_order:
				continue
			wanted = _variant_key(r.item_code)
			for dn in frappe.db.sql(
				"""select dn.name, dn.customer, dn.posting_date, dni.item_code, dni.stock_qty, dni.stock_uom
				from `tabDelivery Note Item` dni join `tabDelivery Note` dn on dn.name = dni.parent
				where dni.against_sales_order = %s and dn.docstatus = 1""",
				sales_order,
				as_dict=True,
			):
				if dn.item_code != r.item_code and _variant_key(dn.item_code) != wanted:
					continue
				key = ("Delivery Note", dn.name, dn.item_code)
				if key in seen:
					continue
				seen.add(key)
				out.append(frappe._dict(customer=dn.customer, voucher_type="Delivery Note", voucher_no=dn.name,
					posting_date=dn.posting_date, item_code=dn.item_code, qty=dn.stock_qty, uom=dn.stock_uom,
					depth=r.indent + 1, via=r.voucher_no))
	return sorted(out, key=lambda r: (r.posting_date or getdate("1900-01-01"), r.voucher_no))


def _variant_key(item_code: str) -> tuple:
	"""Style-independent identity of a variant (its attribute values), so washed and unwashed sizes match."""
	return tuple(sorted(frappe.get_all("Item Variant Attribute", filters={"parent": item_code}, pluck="attribute_value"))) or (item_code,)


def giveaway_cost(filters) -> list[dict]:
	"""Over-weight give-away by item: checks, pieces, average variance, kg and value given away."""
	groups: dict[str, dict] = {}
	for r in ht.weight_checks(filters):
		g = groups.setdefault(r.item_code, frappe._dict(item_code=r.item_code, checks=0, failed=0, pieces=0,
			weighted_variance=0, giveaway_kg=0, giveaway_value=0, target_weight_kg=r.target_weight_kg))
		g.checks += 1
		g.failed += 1 if (r.result or "").lower() not in ("pass", "accepted", "ok") else 0
		g.pieces += flt(r.pieces)
		g.weighted_variance += flt(r.variance_pct) * flt(r.pieces)
		g.giveaway_kg += flt(r.giveaway_kg)
		g.giveaway_value += flt(r.giveaway_value)
	for g in groups.values():
		g.avg_variance_pct = g.weighted_variance / g.pieces if g.pieces else None
		g.giveaway_per_1000 = g.giveaway_value / g.pieces * 1000 if g.pieces else 0
	return sorted(groups.values(), key=lambda r: -r.giveaway_value)


def downtime_mtbf(filters) -> list[dict]:
	"""Per machine: stops, downtime, run time, MTBF and MTTR (logged stops + shift-sheet stops)."""
	f = frappe._dict(filters or {})
	stages = (f.stage,) if f.get("stage") else PRODUCTION_STAGES
	ctx = _ctx(f, stages=stages)
	down = kpi.downtime_minutes(ctx, stages)
	run = kpi.run_minutes(ctx, stages)
	events: dict[str, int] = defaultdict(int)
	reasons: dict[str, dict] = defaultdict(lambda: defaultdict(float))
	for r in frappe.db.sql(
		"""select workstation, reason, count(*) n, sum(duration_min) m from `tabMachine Downtime Log`
		where docstatus = 1 and is_planned = 0 and posting_date between %(from_date)s and %(to_date)s and stage in %(stages)s
		group by workstation, reason""",
		{**ctx, "stages": tuple(stages)},
		as_dict=True,
	):
		events[r.workstation] += r.n
		reasons[r.workstation][r.reason or _("Unspecified")] += flt(r.m)
	for r in kpi.shift_rows(ctx, stages):
		if r.stop_minutes and r.machine not in reasons:
			events[r.machine] += 1
			reasons[r.machine][_("Shift-sheet stops")] += r.stop_minutes
	out = []
	for machine in sorted(set(down) | set(run)):
		down_h, run_h, n = flt(down.get(machine)) / 60, max(flt(run.get(machine)), 0) / 60, events.get(machine, 0)
		if not down_h and not f.get("show_all"):
			continue
		top = max(reasons[machine].items(), key=lambda x: x[1])[0] if reasons.get(machine) else None
		out.append(frappe._dict(
			workstation=machine, stage=frappe.get_cached_value("Workstation", machine, "dm_stage"), stops=n,
			downtime_hours=down_h, run_hours=run_h, availability_pct=run_h / (run_h + down_h) * 100 if run_h + down_h else None,
			mtbf_hours=run_h / n if n else None, mttr_hours=down_h / n if n else None, top_reason=top,
		))
	return sorted(out, key=lambda r: -r.downtime_hours)


# ================================================================ detail / operational reports
def shift_register(filters) -> list[dict]:
	"""Machine-level output per shift from loom and knitting shift sheets."""
	f = frappe._dict(filters or {})
	out = []
	if f.get("machine_type") in (None, "", "Loom"):
		for r in rl.loom_efficiency(f):
			out.append(frappe._dict(posting_date=r.posting_date, shift=r.shift, reference_doctype="Loom Shift Production",
				reference_name=r.loom_shift_production, machine_type=r.loom_type or "Air-jet Denim", machine=r.loom,
				operator=r.weaver, operator_name=_employee_name(r.weaver), output=flt(r.meters) or flt(r.kg),
				uom="Meter" if flt(r.meters) else "Kg", efficiency_pct=r.efficiency_pct,
				faults=flt(r.warp_breaks) + flt(r.weft_breaks), fault_type=_("Breaks"), stop_minutes=r.stop_minutes))
	if f.get("machine_type") in (None, "", "Knitting"):
		for r in kn.knitting_rows(f):
			out.append(frappe._dict(posting_date=r.posting_date, shift=r.shift, reference_doctype="Knitting Shift Production",
				reference_name=r.knitting_shift_production, machine_type="Circular Knitting", machine=r.machine,
				operator=r.operator, operator_name=_employee_name(r.operator), output=flt(r.kg), uom="Kg",
				efficiency_pct=r.efficiency_pct, faults=flt(r.defects_count), fault_type=_("Defects"), stop_minutes=r.stop_minutes,
				rolls=r.rolls_produced))
	if f.get("operator"):
		out = [r for r in out if r.operator == f.operator]
	return sorted(out, key=lambda r: (r.posting_date, r.shift or "", r.machine or ""))


def operator_performance(filters) -> list[dict]:
	"""Weaver / knitter league table: shifts, output, output-weighted efficiency, faults per shift, stops."""
	groups: dict[tuple, dict] = {}
	for r in shift_register(filters):
		key = (r.operator, r.uom)
		g = groups.setdefault(key, frappe._dict(operator=r.operator, operator_name=r.operator_name, machine_type=r.machine_type,
			uom=r.uom, shifts=0, machines=set(), output=0, weighted_eff=0, faults=0, stop_minutes=0))
		g.shifts += 1
		g.machines.add(r.machine)
		g.output += flt(r.output)
		g.weighted_eff += flt(r.efficiency_pct) * flt(r.output)
		g.faults += flt(r.faults)
		g.stop_minutes += flt(r.stop_minutes)
	out = []
	for g in groups.values():
		g.machines = len(g.machines)
		g.efficiency_pct = g.weighted_eff / g.output if g.output else None
		g.output_per_shift = g.output / g.shifts if g.shifts else 0
		g.faults_per_shift = g.faults / g.shifts if g.shifts else 0
		out.append(g)
	out.sort(key=lambda r: -(r.efficiency_pct or 0))
	for rank, r in enumerate(out, 1):
		r.rank = rank
	return out


def defect_pareto(filters) -> list[dict]:
	"""Fabric defects by type: occurrences, penalty points, share and cumulative share (Pareto)."""
	f, company, from_date, to_date = rl._period(filters)
	rows = frappe.db.sql(
		f"""select d.defect_type, count(*) occurrences, sum(d.points) points, count(distinct concat(p.name, d.roll_no)) rolls
		from `tabFabric Roll Defect` d join `tabFabric Roll Inspection` p on p.name = d.parent
		where p.docstatus = 1 and p.inspection_date between %(from)s and %(to)s
		{"and p.company = %(company)s" if company else ""} {"and p.lot_item = %(item)s" if f.get("item_code") else ""}
		group by d.defect_type order by points desc""",  # noqa: S608
		{"from": from_date, "to": to_date, "company": company, "item": f.get("item_code")},
		as_dict=True,
	)
	total = sum(flt(r.points) for r in rows) or 1
	running = 0
	for r in rows:
		running += flt(r.points)
		r.share_pct = flt(r.points) / total * 100
		r.cumulative_pct = running / total * 100
		r.vital_few = 1 if running - flt(r.points) < 0.8 * total else 0
	return rows


def dye_house_log(filters) -> list[dict]:
	"""Every dye-house batch: machine, recipe, input/output, yield, chemical cost per unit, load and re-dye flag."""
	f = frappe._dict(filters or {})
	stages = (f.stage,) if f.get("stage") else DYE_HOUSE_STAGES
	out = []
	for r in rl.stage_yield({**f, "group_by_work_order": 1}):
		if r.dm_stage not in stages:
			continue
		wo = frappe.db.get_value("Work Order", r.work_order, ["dye_recipe", "machine_load_pct", "qty"], as_dict=True) if r.work_order else {}
		machine = frappe.db.get_value("Work Order Operation", {"parent": r.work_order}, "workstation", order_by="idx asc") if r.work_order else None
		corrective = frappe.db.exists("Job Card", {"work_order": r.work_order, "is_corrective_job_card": 1, "docstatus": 1}) if r.work_order else None
		out.append(frappe._dict(
			work_order=r.work_order, posting_date=r.posting_date, stage=r.dm_stage, workstation=machine,
			dye_recipe=(wo or {}).get("dye_recipe"), item_code=r.output_item, uom=r.output_uom, input_qty=r.input_qty,
			output_qty=r.output_qty, yield_pct=r.yield_pct, chemical_cost=r.consumable_cost,
			chemical_cost_per_unit=flt(r.consumable_cost) / flt(r.output_qty) if flt(r.output_qty) else 0,
			machine_load_pct=(wo or {}).get("machine_load_pct") or None, redyed=1 if corrective else 0,
		))
	return out


def chemical_consumption(filters) -> list[dict]:
	"""Chemicals and dyes consumed per stage, per unit of stage output."""
	f, company, from_date, to_date = rl._period(filters)
	rows = frappe.db.sql(
		f"""select se.dm_stage stage, d.item_code, i.item_name, d.stock_uom uom, sum(d.transfer_qty) qty, sum(d.amount) amount
		from `tabStock Entry Detail` d join `tabStock Entry` se on se.name = d.parent join `tabItem` i on i.name = d.item_code
		where se.docstatus = 1 and se.purpose = 'Manufacture' and ifnull(d.s_warehouse, '') != '' and i.item_group = %(group)s
		and se.posting_date between %(from)s and %(to)s {"and se.company = %(company)s" if company else ""}
		{"and se.dm_stage = %(stage)s" if f.get("stage") else ""}
		group by se.dm_stage, d.item_code order by se.dm_stage, amount desc""",  # noqa: S608
		{"group": CHEMICAL_GROUP, "from": from_date, "to": to_date, "company": company, "stage": f.get("stage")},
		as_dict=True,
	)
	output = {s.stage: s for s in rl.stage_yield_summary(f)}
	for r in rows:
		s = output.get(r.stage) or frappe._dict()
		r.stage_output = flt(s.output_qty)
		r.output_uom = s.output_uom
		r.qty_per_1000 = flt(r.qty) / r.stage_output * 1000 if r.stage_output else None
		r.cost_per_unit = flt(r.amount) / r.stage_output if r.stage_output else None
	return rows


def utility_cost_per_unit(filters) -> list[dict]:
	"""Absorbed vs actual utility cost per stage and per unit of stage output."""
	f, company, from_date, to_date = rl._period(filters)
	absorbed = rl.absorbed_utilities(company, from_date, to_date)
	actual = rl.actual_utilities(company, from_date, to_date)
	output = {s.stage: s for s in rl.stage_yield_summary(f)}
	out = []
	for stage in [s for s in PRODUCTION_STAGES if s in absorbed or s in actual]:
		s = output.get(stage) or frappe._dict()
		qty = flt(s.output_qty)
		a, b = absorbed.get(stage, 0), actual.get(stage, 0)
		out.append(frappe._dict(stage=stage, output_qty=qty, uom=s.output_uom, absorbed=a, actual=b, variance=b - a,
			absorbed_per_unit=a / qty if qty else None, actual_per_unit=b / qty if qty else None,
			variance_pct=(b - a) / a * 100 if a else None))
	return out


def waste_recovery(filters) -> list[dict]:
	"""Waste and by-products generated in production vs sold: qty, book value, sales value and recovery."""
	f, company, from_date, to_date = rl._period(filters)
	values = {"from": from_date, "to": to_date, "company": company, "group": WASTE_ITEM_GROUP}
	generated = frappe.db.sql(
		f"""select d.item_code, d.stock_uom uom, group_concat(distinct se.dm_stage) stages, sum(d.transfer_qty) qty, sum(d.amount) value
		from `tabStock Entry Detail` d join `tabStock Entry` se on se.name = d.parent join `tabItem` i on i.name = d.item_code
		where se.docstatus = 1 and d.is_scrap_item = 1 and i.item_group = %(group)s and se.posting_date between %(from)s and %(to)s
		{"and se.company = %(company)s" if company else ""} group by d.item_code""",  # noqa: S608
		values,
		as_dict=True,
	)
	sold = {r.item_code: r for r in frappe.db.sql(
		f"""select sii.item_code, sum(sii.stock_qty) qty, sum(sii.base_net_amount) amount
		from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent join `tabItem` i on i.name = sii.item_code
		where si.docstatus = 1 and i.item_group = %(group)s and si.posting_date between %(from)s and %(to)s
		{"and si.company = %(company)s" if company else ""} group by sii.item_code""",  # noqa: S608
		values,
		as_dict=True,
	)}
	out = []
	for code in sorted({g.item_code for g in generated} | set(sold)):
		g = next((x for x in generated if x.item_code == code), frappe._dict())
		s = sold.get(code) or frappe._dict()
		out.append(frappe._dict(item_code=code, uom=g.uom or frappe.get_cached_value("Item", code, "stock_uom"),
			stages=(g.stages or "").replace(",", ", "), generated_qty=flt(g.qty), book_value=flt(g.value), sold_qty=flt(s.qty),
			sales_value=flt(s.amount), unsold_qty=flt(g.qty) - flt(s.qty),
			sold_pct=flt(s.qty) / flt(g.qty) * 100 if flt(g.qty) else None,
			realised_rate=flt(s.amount) / flt(s.qty) if flt(s.qty) else None))
	return out


def subcontract_reconciliation(filters) -> list[dict]:
	"""Subcontracting orders: material sent vs consumed vs returned, and finished goods ordered vs received."""
	f, company, from_date, to_date = rl._period(filters)
	orders = frappe.db.sql(
		f"""select name, supplier, transaction_date, status from `tabSubcontracting Order`
		where docstatus = 1 and transaction_date between %(from)s and %(to)s {"and company = %(company)s" if company else ""}
		{"and supplier = %(supplier)s" if f.get("supplier") else ""} order by transaction_date""",  # noqa: S608
		{"from": from_date, "to": to_date, "company": company, "supplier": f.get("supplier")},
		as_dict=True,
	)
	out = []
	for o in orders:
		for i in frappe.get_all("Subcontracting Order Item", filters={"parent": o.name}, fields=["item_code", "qty", "received_qty", "stock_uom"]):
			out.append(frappe._dict(subcontracting_order=o.name, supplier=o.supplier, transaction_date=o.transaction_date,
				status=o.status, line_type=_("Finished goods"), item_code=i.item_code, uom=i.stock_uom, ordered_qty=i.qty,
				received_qty=i.received_qty, pending_qty=flt(i.qty) - flt(i.received_qty)))
		for s in frappe.get_all("Subcontracting Order Supplied Item", filters={"parent": o.name},
				fields=["rm_item_code", "required_qty", "supplied_qty", "consumed_qty", "returned_qty", "stock_uom"]):
			balance = flt(s.supplied_qty) - flt(s.consumed_qty) - flt(s.returned_qty)
			out.append(frappe._dict(subcontracting_order=o.name, supplier=o.supplier, transaction_date=o.transaction_date,
				status=o.status, line_type=_("Material sent"), item_code=s.rm_item_code, uom=s.stock_uom,
				ordered_qty=s.required_qty, supplied_qty=s.supplied_qty, consumed_qty=s.consumed_qty,
				returned_qty=s.returned_qty, balance_with_supplier=balance))
	return out


def marker_efficiency(filters) -> list[dict]:
	"""Cut plans: pieces cut vs ordered (over-cut), fabric per piece and cutting variance."""
	f, company, from_date, to_date = rl._period(filters)
	plans = frappe.get_all(
		"Cut Plan",
		filters={"docstatus": 1, "posting_date": ["between", [from_date, to_date]], **({"company": company} if company else {})},
		fields=["name", "posting_date", "sales_order", "style_template", "fabric_item", "fabric_uom", "marker_length_m",
			"pieces_per_marker", "plies", "end_bit_allowance_pct", "total_pieces", "fabric_required_m", "fabric_issued_m",
			"standard_fabric_m", "cutting_variance_m", "cutting_variance_pct", "status"],
		order_by="posting_date",
	)
	for p in plans:
		variants = [s.variant_item for s in frappe.get_all("Cut Plan Size", filters={"parent": p.name}, fields=["variant_item"])]
		p.ordered_pieces = flt(frappe.db.sql(
			"select sum(stock_qty) from `tabSales Order Item` where parent = %s and item_code in %s",
			(p.sales_order, tuple(variants) or ("",)))[0][0]) if p.sales_order else 0
		p.over_cut = flt(p.total_pieces) - p.ordered_pieces if p.ordered_pieces else None
		p.over_cut_pct = p.over_cut / p.ordered_pieces * 100 if p.ordered_pieces else None
		p.fabric_per_piece = flt(p.fabric_issued_m) / flt(p.total_pieces) if flt(p.total_pieces) else None
		p.marker_fabric = flt(p.marker_length_m) * flt(p.plies)
	return plans


def bundle_wip(filters) -> list[dict]:
	"""Bundle tickets by cut plan, size, line and status with pieces and age."""
	f = frappe._dict(filters or {})
	as_on = getdate(f.get("to_date") or today())
	conditions = ["1 = 1"]
	if f.get("status"):
		conditions.append("b.status = %(status)s")
	if f.get("cut_plan"):
		conditions.append("b.cut_plan = %(cut_plan)s")
	rows = frappe.db.sql(
		f"""select b.cut_plan, b.work_order, b.variant_item, b.size, ifnull(b.stitch_line, '') stitch_line, b.status,
			count(*) bundles, sum(b.qty) pieces, min(cp.posting_date) oldest, max(b.stitched_on) last_stitched
		from `tabBundle Ticket` b join `tabCut Plan` cp on cp.name = b.cut_plan where {" and ".join(conditions)}
		group by b.cut_plan, b.work_order, b.variant_item, b.size, b.stitch_line, b.status
		order by b.cut_plan, b.size, b.status""",  # noqa: S608
		f,
		as_dict=True,
	)
	for r in rows:
		r.age_days = date_diff(as_on, r.oldest) if r.status not in ("Stitched", "Rejected") else 0
	return rows


def order_book_by_line(filters) -> list[dict]:
	"""Open order book split by business line (Denim, Home Textile, Knitting)."""
	f = frappe._dict(filters or {})
	rows = late_order_risk({"company": f.get("company"), "customer": f.get("customer"), "as_on_date": f.get("as_on_date")})
	if f.get("business_line"):
		rows = [r for r in rows if r.business_line == f.business_line]
	return sorted(rows, key=lambda r: (r.business_line, r.delivery_date or getdate("2100-01-01")))
