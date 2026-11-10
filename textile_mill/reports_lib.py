"""Shared report logic (Part B §9). Script reports, number cards, dashboards and the demo summary
all read from here so every screen shows the same numbers."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from textile_mill.constants import CONSUMABLE_ITEM_GROUPS, UTILITY_ABSORBED_PREFIX, WASTE_ITEM_GROUP

OPERATING_PREFIX = "Operating Cost"
CORRECTIVE_PREFIX = "Corrective"
PRODUCING_PURPOSES = ("Manufacture", "Repack")


def _period(filters) -> tuple:
	f = frappe._dict(filters or {})
	return f, f.get("company"), getdate(f.get("from_date") or "2000-01-01"), getdate(f.get("to_date") or "2100-12-31")


def _in(values) -> tuple:
	return tuple(values) or ("",)


# ---------------------------------------------------------------- manufacture entries
def manufacture_entries(filters) -> list[dict]:
	"""One row per submitted Manufacture Stock Entry with input/output/scrap/cost aggregates."""
	f, company, from_date, to_date = _period(filters)
	conditions = ["se.docstatus = 1", "se.purpose = 'Manufacture'", "se.posting_date between %(from)s and %(to)s"]
	values = {"from": from_date, "to": to_date, "consumables": _in(CONSUMABLE_ITEM_GROUPS)}
	for key, column in (("company", "se.company"), ("dm_stage", "se.dm_stage"), ("work_order", "se.work_order")):
		if f.get(key):
			conditions.append(f"{column} = %({key})s")
			values[key] = f.get(key)
	if f.get("item_code"):
		conditions.append("exists (select 1 from `tabStock Entry Detail` x where x.parent = se.name and x.is_finished_item = 1 and x.item_code = %(item_code)s)")
		values["item_code"] = f.item_code

	rows = frappe.db.sql(
		f"""
		select se.name as stock_entry, se.posting_date, se.work_order, se.dm_stage, se.bom_no,
			se.total_additional_costs,
			sum(if(d.is_finished_item = 1, d.transfer_qty, 0)) as output_qty,
			max(if(d.is_finished_item = 1, d.item_code, null)) as output_item,
			max(if(d.is_finished_item = 1, d.stock_uom, null)) as output_uom,
			sum(if(d.is_finished_item = 1, d.amount, 0)) as output_value,
			sum(if(ifnull(d.s_warehouse, '') != '' and i.item_group not in %(consumables)s, d.transfer_qty, 0)) as input_qty,
			group_concat(distinct if(ifnull(d.s_warehouse, '') != '' and i.item_group not in %(consumables)s, d.stock_uom, null)) as input_uoms,
			sum(if(ifnull(d.s_warehouse, '') != '', d.amount, 0)) as material_cost,
			sum(if(ifnull(d.s_warehouse, '') != '' and i.item_group in %(consumables)s, d.amount, 0)) as consumable_cost,
			sum(if(d.is_scrap_item = 1, d.transfer_qty, 0)) as scrap_qty,
			sum(if(d.is_scrap_item = 1, d.amount, 0)) as scrap_value
		from `tabStock Entry` se
		join `tabStock Entry Detail` d on d.parent = se.name
		join `tabItem` i on i.name = d.item_code
		where {" and ".join(conditions)}
		group by se.name
		order by se.posting_date, se.posting_time, se.name
		""",  # noqa: S608
		values,
		as_dict=True,
	)
	costs = additional_cost_split([r.stock_entry for r in rows])
	for r in rows:
		r.update(costs.get(r.stock_entry, {"operating_cost": 0, "corrective_cost": 0, "utilities_absorbed": 0, "other_cost": 0}))
	return rows


def additional_cost_split(stock_entries: list[str]) -> dict[str, dict]:
	out = defaultdict(lambda: {"operating_cost": 0.0, "corrective_cost": 0.0, "utilities_absorbed": 0.0, "other_cost": 0.0})
	if not stock_entries:
		return out
	for c in frappe.get_all(
		"Landed Cost Taxes and Charges",
		filters={"parenttype": "Stock Entry", "parent": ["in", stock_entries]},
		fields=["parent", "description", "base_amount", "amount"],
	):
		desc = c.description or ""
		amount = flt(c.base_amount or c.amount)
		if desc.startswith(UTILITY_ABSORBED_PREFIX):
			out[c.parent]["utilities_absorbed"] += amount
		elif desc.startswith(CORRECTIVE_PREFIX):
			out[c.parent]["corrective_cost"] += amount
		elif desc.startswith(OPERATING_PREFIX):
			out[c.parent]["operating_cost"] += amount
		else:
			out[c.parent]["other_cost"] += amount
	return out


def _group_by_work_order(rows: list[dict]) -> list[dict]:
	sums = ("output_qty", "output_value", "input_qty", "material_cost", "consumable_cost", "scrap_qty", "scrap_value",
		"operating_cost", "corrective_cost", "utilities_absorbed", "other_cost", "total_additional_costs")
	grouped: dict[str, dict] = {}
	for r in rows:
		key = r.work_order or r.stock_entry
		g = grouped.get(key)
		if not g:
			grouped[key] = frappe._dict(r, stock_entry=None)
			continue
		for s in sums:
			g[s] = flt(g[s]) + flt(r[s])
		g.posting_date = max(g.posting_date, r.posting_date)
	return list(grouped.values())


# ---------------------------------------------------------------- 9.1 stage yield
def stage_yield(filters) -> list[dict]:
	rows = manufacture_entries(filters)
	if (filters or {}).get("group_by_work_order"):
		rows = _group_by_work_order(rows)
	for r in rows:
		same_uom = (r.input_uoms or "") == (r.output_uom or "")
		inp = flt(r.input_qty)
		r.same_uom = same_uom
		r.output_per_input = flt(r.output_qty) / inp if inp else 0
		r.yield_pct = flt(r.output_qty) / inp * 100 if inp and same_uom else None
		r.waste_pct = flt(r.scrap_qty) / inp * 100 if inp and same_uom else None
		r.loss_qty = inp - flt(r.output_qty) - flt(r.scrap_qty) if same_uom else None
		r.loss_pct = flt(r.loss_qty) / inp * 100 if inp and same_uom else None
	return rows


def stage_yield_summary(filters) -> list[dict]:
	"""Yield by stage (weighted), used by charts, cards and the console summary."""
	by_stage: dict[str, dict] = {}
	for r in stage_yield(filters):
		key = r.dm_stage or "Unstaged"
		s = by_stage.setdefault(key, frappe._dict(stage=key, output_qty=0, input_qty=0, scrap_qty=0, output_uom=r.output_uom,
			same_uom=r.same_uom, output_value=0, std_value=0))
		s.output_qty += flt(r.output_qty)
		s.input_qty += flt(r.input_qty)
		s.scrap_qty += flt(r.scrap_qty)
		s.output_value += flt(r.output_value)
		s.same_uom = s.same_uom and r.same_uom
	for s in by_stage.values():
		s.yield_pct = s.output_qty / s.input_qty * 100 if s.input_qty and s.same_uom else None
		s.waste_pct = s.scrap_qty / s.input_qty * 100 if s.input_qty and s.same_uom else None
		s.output_per_input = s.output_qty / s.input_qty if s.input_qty else 0
		s.cost_per_unit = s.output_value / s.output_qty if s.output_qty else 0
	return list(by_stage.values())


# ---------------------------------------------------------------- 9.2 cost per unit
def _utility_rate(stage: str | None) -> float:
	if not stage:
		return 0
	return flt(frappe.db.get_value("Stage Utility Rate", {"parent": "Textile Mill Settings", "stage": stage}, "rate_per_output_uom"))


def standard_cost(item_code: str, memo: dict | None = None) -> float:
	"""Rolled-up standard cost per stock unit.

	Bought items use the Standard Buying price; made items use their default BOM quantities with every
	input at its own standard, plus BOM operating cost and the stage utility rate, less scrap at standard.
	Graded fabric is valued at the lot's standard scaled by its relative sales value against the top grade.
	"""
	memo = {} if memo is None else memo
	if item_code in memo:
		return memo[item_code]
	memo[item_code] = 0

	grade = frappe.db.get_value("Fabric Grade Map", {"graded_item": item_code}, ["lot_item", "relative_sales_value"], as_dict=True)
	bom_no = frappe.db.get_value("BOM", {"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1})
	if grade:
		top = flt(frappe.db.get_value("Fabric Grade Map", {"lot_item": grade.lot_item}, "max(relative_sales_value)"))
		rate = standard_cost(grade.lot_item, memo) * (flt(grade.relative_sales_value) / top if top else 1)
	elif bom_no:
		bom = frappe.get_cached_doc("BOM", bom_no)
		inputs = sum(flt(i.stock_qty) * standard_cost(i.item_code, memo) for i in bom.items)
		scrap = sum(flt(s.stock_qty) * standard_cost(s.item_code, memo) for s in bom.scrap_items)
		stage = frappe.get_cached_value("Item", item_code, "dm_stage")
		rate = (inputs + flt(bom.base_operating_cost or bom.operating_cost) - scrap) / flt(bom.quantity or 1) + _utility_rate(stage)
	else:
		rate = flt(frappe.db.get_value("Item Price", {"item_code": item_code, "buying": 1}, "price_list_rate")) or flt(
			frappe.get_cached_value("Item", item_code, "valuation_rate")
		)
	memo[item_code] = rate
	return rate


def standard_cost_per_unit(bom_no: str | None, stage: str | None, memo: dict | None = None) -> float:
	item = frappe.db.get_value("BOM", bom_no, "item") if bom_no else None
	return standard_cost(item, memo) if item else 0


def cost_per_unit(filters) -> list[dict]:
	rows = _group_by_work_order(manufacture_entries(filters))
	memo: dict = {}
	for r in rows:
		r.total_actual_cost = flt(r.output_value)
		r.actual_per_unit = r.total_actual_cost / flt(r.output_qty) if flt(r.output_qty) else 0
		r.standard_per_unit = standard_cost(r.output_item, memo) if r.output_item else 0
		r.variance_per_unit = r.actual_per_unit - r.standard_per_unit
		r.variance_pct = r.variance_per_unit / r.standard_per_unit * 100 if r.standard_per_unit else None
	return rows


def cost_per_unit_by_stage(filters) -> list[dict]:
	by_stage: dict[str, dict] = {}
	for r in cost_per_unit(filters):
		key = r.dm_stage or "Unstaged"
		s = by_stage.setdefault(key, frappe._dict(stage=key, output_qty=0, actual=0, standard=0, output_uom=r.output_uom))
		s.output_qty += flt(r.output_qty)
		s.actual += r.total_actual_cost
		s.standard += r.standard_per_unit * flt(r.output_qty)
	for s in by_stage.values():
		s.actual_per_unit = s.actual / s.output_qty if s.output_qty else 0
		s.standard_per_unit = s.standard / s.output_qty if s.output_qty else 0
		s.variance_pct = (s.actual_per_unit - s.standard_per_unit) / s.standard_per_unit * 100 if s.standard_per_unit else None
	return list(by_stage.values())


# ---------------------------------------------------------------- 9.3 recipe variance
def recipe_variance(filters) -> list[dict]:
	f = frappe._dict(filters or {})
	entries = [r for r in _group_by_work_order(manufacture_entries(f)) if r.work_order]
	out = []
	for e in entries:
		recipe_name = frappe.db.get_value("Work Order", e.work_order, "dye_recipe")
		if not recipe_name or (f.get("dye_recipe") and recipe_name != f.dye_recipe):
			continue
		recipe = frappe.get_cached_doc("Dye Recipe", recipe_name)
		consumed = frappe.db.sql(
			"""select d.item_code, sum(d.transfer_qty) qty, sum(d.amount) amount
			from `tabStock Entry Detail` d join `tabStock Entry` se on se.name = d.parent
			where se.docstatus = 1 and se.purpose = 'Manufacture' and se.work_order = %s and ifnull(d.s_warehouse, '') != ''
			group by d.item_code""",
			e.work_order,
			as_dict=True,
		)
		used = {c.item_code: c for c in consumed}
		base = flt(used.get(recipe.base_item, {}).get("qty"))
		total = frappe._dict(work_order=e.work_order, dye_recipe=recipe_name, item_code=_("Total"), is_total=1,
			standard_qty=0, actual_qty=0, variance_amount=0, base_qty=base)
		for chem in recipe.chemicals:
			c = used.get(chem.item_code, {})
			actual = flt(c.get("qty"))
			standard = flt(chem.g_per_kg) * base / 1000
			rate = flt(c.get("amount")) / actual if actual else flt(chem.rate)
			row = frappe._dict(
				work_order=e.work_order, dye_recipe=recipe_name, stage=e.dm_stage, item_code=chem.item_code, base_qty=base,
				recipe_g_per_kg=flt(chem.g_per_kg), standard_qty=standard, actual_qty=actual,
				actual_g_per_kg=actual / base * 1000 if base else 0, variance_qty=actual - standard,
				variance_pct=(actual - standard) / standard * 100 if standard else None,
				variance_amount=(actual - standard) * rate,
			)
			out.append(row)
			total.standard_qty += standard
			total.actual_qty += actual
			total.variance_amount += row.variance_amount
		out.append(total)
	return out


# ---------------------------------------------------------------- 9.4 loom efficiency
def loom_efficiency(filters) -> list[dict]:
	f, _company, from_date, to_date = _period(filters)
	conditions = ["p.docstatus = 1", "p.posting_date between %(from)s and %(to)s"]
	values = {"from": from_date, "to": to_date}
	for key, column in (("shift", "p.shift"), ("loom", "r.loom"), ("weaver", "r.weaver"), ("loom_type", "p.loom_type")):
		if f.get(key):
			conditions.append(f"{column} = %({key})s")
			values[key] = f.get(key)
	return frappe.db.sql(
		f"""select p.name as loom_shift_production, p.posting_date, p.shift, p.loom_type, r.loom, r.weaver, r.rpm, r.picks_per_inch,
			r.meters, r.kg, r.efficiency_pct, r.warp_breaks, r.weft_breaks, r.stop_minutes,
			if(r.meters > 0, (r.warp_breaks + r.weft_breaks) / (r.meters * 39.37 * r.picks_per_inch) * 100000, 0) as breaks_per_100k_picks
		from `tabLoom Shift Row` r join `tabLoom Shift Production` p on p.name = r.parent
		where {" and ".join(conditions)}
		order by p.posting_date, p.shift, r.idx""",  # noqa: S608
		values,
		as_dict=True,
	)


def weighted_loom_efficiency(filters) -> float:
	"""Output-weighted efficiency: metres for denim/flat looms, kg for terry looms."""
	rows = loom_efficiency(filters)
	weights = [flt(r.meters) or flt(r.kg) for r in rows]
	total = sum(weights)
	return sum(flt(r.efficiency_pct) * w for r, w in zip(rows, weights)) / total if total else 0


# ---------------------------------------------------------------- 9.5 fabric grade
def fabric_grades(filters) -> list[dict]:
	f, company, from_date, to_date = _period(filters)
	conditions = ["p.docstatus = 1", "p.inspection_date between %(from)s and %(to)s"]
	values = {"from": from_date, "to": to_date}
	if company:
		conditions.append("p.company = %(company)s")
		values["company"] = company
	rows = frappe.db.sql(
		f"""select p.name as fabric_roll_inspection, p.lot_item, p.lot_batch, p.inspection_date,
			count(r.name) as rolls, sum(r.length_m) as meters,
			sum(if(r.grade = 'A', r.length_m, 0)) as a_m, sum(if(r.grade = 'B', r.length_m, 0)) as b_m,
			sum(if(r.grade = 'Rejected', r.length_m, 0)) as rejected_m,
			sum(r.points_per_100_sq_yd * r.length_m) / sum(r.length_m) as avg_points
		from `tabFabric Roll Inspection` p join `tabFabric Roll` r on r.parent = p.name
		where {" and ".join(conditions)}
		group by p.name order by p.inspection_date""",  # noqa: S608
		values,
		as_dict=True,
	)
	for r in rows:
		m = flt(r.meters) or 1
		r.a_pct, r.b_pct, r.rejected_pct = (flt(r.a_m) / m * 100, flt(r.b_m) / m * 100, flt(r.rejected_m) / m * 100)
		top = frappe.db.sql(
			"""select defect_type, sum(points) pts from `tabFabric Roll Defect` where parent = %s
			group by defect_type order by pts desc limit 3""",
			r.fabric_roll_inspection,
		)
		r.top_defects = ", ".join(f"{d} ({int(p)})" for d, p in top)
	return rows


def grade_split(filters) -> dict:
	rows = fabric_grades(filters)
	meters = sum(flt(r.meters) for r in rows)
	split = {g: sum(flt(r[f"{k}_m"]) for r in rows) for g, k in (("A", "a"), ("B", "b"), ("Rejected", "rejected"))}
	return {"meters": meters, **split, **{f"{g}_pct": (v / meters * 100 if meters else 0) for g, v in split.items()}}


# ---------------------------------------------------------------- 9.6 corrective
def corrective_jobs(filters) -> list[dict]:
	f, company, from_date, to_date = _period(filters)
	values = {"from": from_date, "to": to_date, "company": company}
	rows = frappe.db.sql(
		f"""select jc.name as job_card, jc.work_order, wo.dm_stage, jc.operation, jc.for_operation, jc.workstation,
			jc.total_time_in_mins / 60 as hours, jc.hour_rate, jc.total_time_in_mins / 60 * jc.hour_rate as cost,
			jc.remarks as reason, jc.posting_date
		from `tabJob Card` jc join `tabWork Order` wo on wo.name = jc.work_order
		where jc.docstatus = 1 and jc.is_corrective_job_card = 1 and jc.posting_date between %(from)s and %(to)s
		{"and jc.company = %(company)s" if company else ""}
		order by jc.posting_date""",  # noqa: S608
		values,
		as_dict=True,
	)
	return rows


def redye_pct_by_stage(filters) -> dict[str, float]:
	f, company, from_date, to_date = _period(filters)
	rows = frappe.db.sql(
		f"""select wo.dm_stage, count(*) total,
			sum(exists(select 1 from `tabJob Card` jc where jc.work_order = wo.name and jc.is_corrective_job_card = 1 and jc.docstatus = 1)) corrective
		from `tabWork Order` wo
		where wo.docstatus = 1 and date(wo.planned_start_date) between %(from)s and %(to)s
		{"and wo.company = %(company)s" if company else ""}
		group by wo.dm_stage""",  # noqa: S608
		{"from": from_date, "to": to_date, "company": company},
		as_dict=True,
	)
	return {r.dm_stage or "Unstaged": flt(r.corrective) / r.total * 100 for r in rows if r.total}


# ---------------------------------------------------------------- 9.7 utilities
def absorbed_utilities(company: str | None, from_date, to_date) -> dict[str, float]:
	rows = frappe.db.sql(
		f"""select c.description, sum(ifnull(nullif(c.base_amount, 0), c.amount)) amount
		from `tabLanded Cost Taxes and Charges` c join `tabStock Entry` se on se.name = c.parent
		where c.parenttype = 'Stock Entry' and se.docstatus = 1 and se.posting_date between %(from)s and %(to)s
		and c.description like %(prefix)s {"and se.company = %(company)s" if company else ""}
		group by c.description""",  # noqa: S608
		{"from": getdate(from_date), "to": getdate(to_date), "prefix": f"{UTILITY_ABSORBED_PREFIX}%", "company": company},
		as_dict=True,
	)
	return {r.description[len(UTILITY_ABSORBED_PREFIX):].strip(): flt(r.amount) for r in rows}


def actual_utilities(company: str | None, from_date, to_date) -> dict[str, float]:
	rows = frappe.db.sql(
		f"""select l.stage, sum(l.amount) amount
		from `tabUtility Consumption Line` l join `tabUtility Consumption Log` p on p.name = l.parent
		where p.docstatus = 1 and p.period_from >= %(from)s and p.period_to <= %(to)s
		{"and p.company = %(company)s" if company else ""}
		group by l.stage""",  # noqa: S608
		{"from": getdate(from_date), "to": getdate(to_date), "company": company},
		as_dict=True,
	)
	return {r.stage: flt(r.amount) for r in rows}


def utility_variance(filters) -> list[dict]:
	f, company, from_date, to_date = _period(filters)
	absorbed = absorbed_utilities(company, from_date, to_date)
	actual = actual_utilities(company, from_date, to_date)
	out = []
	for stage in sorted(set(absorbed) | set(actual)):
		a, b = absorbed.get(stage, 0), actual.get(stage, 0)
		out.append(frappe._dict(stage=stage, absorbed=a, actual=b, variance=b - a, variance_pct=(b - a) / a * 100 if a else None))
	return out


# ---------------------------------------------------------------- 9.8 genealogy
def _bundle_entries(voucher_no: str, transaction: str) -> list[dict]:
	return frappe.db.sql(
		"""select e.batch_no, abs(e.qty) qty, b.item_code, b.warehouse, b.voucher_detail_no
		from `tabSerial and Batch Entry` e join `tabSerial and Batch Bundle` b on b.name = e.parent
		where b.voucher_no = %s and b.type_of_transaction = %s and b.docstatus = 1 and b.is_cancelled = 0
		and ifnull(e.batch_no, '') != ''""",
		(voucher_no, transaction),
		as_dict=True,
	)


def _producing_voucher(batch_no: str) -> dict | None:
	rows = frappe.db.sql(
		"""select b.voucher_type, b.voucher_no, b.posting_date, b.item_code, sum(abs(e.qty)) qty
		from `tabSerial and Batch Entry` e join `tabSerial and Batch Bundle` b on b.name = e.parent
		left join `tabStock Entry` se on b.voucher_type = 'Stock Entry' and se.name = b.voucher_no
		where e.batch_no = %s and b.type_of_transaction = 'Inward' and b.docstatus = 1 and b.is_cancelled = 0
		and (b.voucher_type in ('Purchase Receipt', 'Subcontracting Receipt')
			or (b.voucher_type = 'Stock Entry' and se.purpose in ('Manufacture', 'Repack', 'Material Receipt')))
		group by b.voucher_no order by b.posting_date, b.creation limit 1""",
		batch_no,
		as_dict=True,
	)
	return rows[0] if rows else None


class _Tree:
	def __init__(self, max_depth: int):
		self.rows: list[dict] = []
		self.max_depth = max_depth
		self.seen: set = set()

	def add(self, parent: str | None, indent: int, **row) -> str:
		name = f"n{len(self.rows) + 1}"
		item = row.get("item_code")
		self.rows.append(
			frappe._dict(
				name=name, parent_node=parent, indent=indent,
				stage=frappe.get_cached_value("Item", item, "dm_stage") if item else None,
				uom=frappe.get_cached_value("Item", item, "stock_uom") if item else None,
				**row,
			)
		)
		return name


def genealogy(filters) -> list[dict]:
	f = frappe._dict(filters or {})
	tree = _Tree(int(f.get("max_depth") or 10))
	if (f.get("direction") or "Backward") == "Forward":
		if not f.get("batch_no"):
			frappe.throw(_("Forward genealogy needs a Batch."))
		_forward(tree, f.batch_no, None, 0)
		return tree.rows
	if f.get("batch_no"):
		_backward(tree, f.batch_no, None, 0)
	elif f.get("work_order"):
		_backward_work_order(tree, f.work_order, None, 0)
	elif f.get("delivery_note"):
		_backward_delivery(tree, f.delivery_note)
	else:
		frappe.throw(_("Set a Batch, Work Order or Delivery Note."))
	return tree.rows


def _backward(tree: _Tree, batch_no: str, parent: str | None, depth: int, qty: float | None = None) -> None:
	item = frappe.db.get_value("Batch", batch_no, "item")
	node = tree.add(parent, depth, node_type="Batch", item_code=item, batch_no=batch_no, qty=qty)
	if depth >= tree.max_depth or batch_no in tree.seen:
		return
	tree.seen.add(batch_no)
	source = _producing_voucher(batch_no)
	if not source:
		return
	row = tree.rows[-1] if tree.rows[-1].name == node else next(r for r in tree.rows if r.name == node)
	row.update(voucher_type=source.voucher_type, voucher_no=source.voucher_no, posting_date=source.posting_date)
	if row.qty is None:
		row.qty = source.qty
	if source.voucher_type == "Purchase Receipt":
		supplier = frappe.db.get_value("Purchase Receipt", source.voucher_no, "supplier")
		tree.add(node, depth + 1, node_type="Supplier", party=supplier, voucher_type="Purchase Receipt",
			voucher_no=source.voucher_no, posting_date=source.posting_date, qty=source.qty)
		return
	if source.voucher_type == "Subcontracting Receipt":
		supplier = frappe.db.get_value("Subcontracting Receipt", source.voucher_no, "supplier")
		tree.add(node, depth + 1, node_type="Supplier", party=supplier, voucher_type=source.voucher_type, voucher_no=source.voucher_no)
	_inputs(tree, source.voucher_type, source.voucher_no, node, depth)


def _inputs(tree: _Tree, voucher_type: str, voucher_no: str, node: str, depth: int) -> None:
	consumables = set(CONSUMABLE_ITEM_GROUPS)
	merged: dict[str, float] = defaultdict(float)
	for e in _bundle_entries(voucher_no, "Outward"):
		merged[e.batch_no] += flt(e.qty)
	for batch, qty in merged.items():
		item = frappe.db.get_value("Batch", batch, "item")
		group = frappe.get_cached_value("Item", item, "item_group")
		if group in consumables:
			tree.add(node, depth + 1, node_type="Consumable", item_code=item, batch_no=batch, qty=qty)
		else:
			_backward(tree, batch, node, depth + 1, qty)
	if voucher_type == "Stock Entry":
		for d in frappe.get_all(
			"Stock Entry Detail",
			filters={"parent": voucher_no, "s_warehouse": ["is", "set"], "batch_no": ["is", "not set"], "serial_and_batch_bundle": ["is", "not set"]},
			fields=["item_code", "transfer_qty"],
		):
			tree.add(node, depth + 1, node_type="Consumable", item_code=d.item_code, qty=d.transfer_qty)


def _backward_work_order(tree: _Tree, work_order: str, parent: str | None, depth: int) -> None:
	wo = frappe.db.get_value("Work Order", work_order, ["production_item", "produced_qty", "cut_plan"], as_dict=True)
	node = tree.add(parent, depth, node_type="Work Order", item_code=wo.production_item, qty=wo.produced_qty,
		voucher_type="Work Order", voucher_no=work_order)
	transfers = frappe.get_all(
		"Stock Entry",
		filters={"work_order": work_order, "docstatus": 1, "purpose": "Material Transfer for Manufacture"},
		pluck="name",
	)
	merged: dict[str, float] = defaultdict(float)
	for se in transfers:
		for e in _bundle_entries(se, "Outward"):
			merged[e.batch_no] += flt(e.qty)
	consumables = set(CONSUMABLE_ITEM_GROUPS)
	for batch, qty in merged.items():
		item = frappe.db.get_value("Batch", batch, "item")
		if frappe.get_cached_value("Item", item, "item_group") in consumables:
			tree.add(node, depth + 1, node_type="Consumable", item_code=item, batch_no=batch, qty=qty)
		else:
			_backward(tree, batch, node, depth + 1, qty)


def _backward_delivery(tree: _Tree, delivery_note: str) -> None:
	dn = frappe.get_doc("Delivery Note", delivery_note)
	node = tree.add(None, 0, node_type="Delivery", party=dn.customer, voucher_type="Delivery Note", voucher_no=dn.name,
		posting_date=dn.posting_date, qty=dn.total_qty)
	for so in {i.against_sales_order for i in dn.items if i.against_sales_order}:
		for cut_plan in frappe.get_all("Cut Plan", filters={"sales_order": so, "docstatus": 1}, pluck="name"):
			for wo in frappe.get_all("Work Order", filters={"cut_plan": cut_plan, "docstatus": 1}, pluck="name"):
				_backward_work_order(tree, wo, node, 1)
	for i in dn.items:
		if i.batch_no:
			_backward(tree, i.batch_no, node, 1, i.stock_qty)


def _forward(tree: _Tree, batch_no: str, parent: str | None, depth: int) -> None:
	item = frappe.db.get_value("Batch", batch_no, "item")
	node = tree.add(parent, depth, node_type="Batch", item_code=item, batch_no=batch_no)
	if depth >= tree.max_depth or batch_no in tree.seen:
		return
	tree.seen.add(batch_no)
	uses = frappe.db.sql(
		"""select b.voucher_type, b.voucher_no, b.posting_date, sum(abs(e.qty)) qty
		from `tabSerial and Batch Entry` e join `tabSerial and Batch Bundle` b on b.name = e.parent
		where e.batch_no = %s and b.type_of_transaction = 'Outward' and b.docstatus = 1 and b.is_cancelled = 0
		group by b.voucher_no order by b.posting_date""",
		batch_no,
		as_dict=True,
	)
	for u in uses:
		if u.voucher_type == "Stock Entry":
			se = frappe.db.get_value("Stock Entry", u.voucher_no, ["purpose", "work_order"], as_dict=True)
			if se.purpose in PRODUCING_PURPOSES:
				outputs = {e.batch_no for e in _bundle_entries(u.voucher_no, "Inward")
					if frappe.get_cached_value("Item", e.item_code, "item_group") != WASTE_ITEM_GROUP}
				for b in sorted(outputs):
					_forward(tree, b, node, depth + 1)
			elif se.purpose == "Material Transfer for Manufacture" and se.work_order:
				wo_item = frappe.db.get_value("Work Order", se.work_order, "production_item")
				if not frappe.get_cached_value("Item", wo_item, "has_batch_no"):
					tree.add(node, depth + 1, node_type="Work Order", item_code=wo_item, qty=u.qty,
						voucher_type="Work Order", voucher_no=se.work_order, posting_date=u.posting_date)
		elif u.voucher_type in ("Delivery Note", "Sales Invoice"):
			customer = frappe.db.get_value(u.voucher_type, u.voucher_no, "customer")
			tree.add(node, depth + 1, node_type="Customer", party=customer, voucher_type=u.voucher_type,
				voucher_no=u.voucher_no, posting_date=u.posting_date, qty=u.qty)


def lineage_path(rows: list[dict], start: str | None = None) -> list[dict]:
	"""First root-to-leaf path through the main lineage (skips consumables)."""
	children = defaultdict(list)
	for r in rows:
		children[r.parent_node].append(r)
	path, node = [], start
	while True:
		nxt = [c for c in children.get(node, []) if c.node_type != "Consumable"]
		if not nxt:
			return path
		path.append(nxt[0])
		node = nxt[0].name


# ---------------------------------------------------------------- 9.9 order profitability
def order_profitability(sales_order: str) -> dict:
	so = frappe.db.get_value("Sales Order", sales_order, ["customer", "grand_total", "net_total", "company"], as_dict=True)
	if not so:
		frappe.throw(_("Sales Order {0} not found").format(sales_order))
	revenue = flt(frappe.db.sql(
		"""select sum(i.base_net_amount) from `tabSales Invoice Item` i join `tabSales Invoice` p on p.name = i.parent
		where p.docstatus = 1 and i.sales_order = %s""", sales_order)[0][0])
	cogs = flt(frappe.db.sql(
		"""select -sum(sle.stock_value_difference) from `tabStock Ledger Entry` sle
		join `tabDelivery Note Item` i on i.name = sle.voucher_detail_no
		where sle.voucher_type = 'Delivery Note' and sle.is_cancelled = 0 and i.against_sales_order = %s""", sales_order)[0][0])

	build_up = []
	for cut_plan in frappe.get_all("Cut Plan", filters={"sales_order": sales_order, "docstatus": 1}, pluck="name"):
		for wo in frappe.get_all("Work Order", filters={"cut_plan": cut_plan, "docstatus": 1}, fields=["name", "production_item"]):
			build_up.append(_garment_build_up(wo.name, wo.production_item))
	margin = revenue - cogs
	return frappe._dict(
		sales_order=sales_order, customer=so.customer, revenue=revenue, cogs=cogs, gross_margin=margin,
		margin_pct=margin / revenue * 100 if revenue else 0, build_up=build_up,
	)


def _garment_build_up(work_order: str, item_code: str) -> dict:
	rows = frappe.db.sql(
		"""select i.item_group, sum(d.amount) amount, sum(if(d.is_finished_item, d.transfer_qty, 0)) fg_qty,
			sum(if(d.is_finished_item, d.amount, 0)) fg_amount
		from `tabStock Entry Detail` d join `tabStock Entry` se on se.name = d.parent join `tabItem` i on i.name = d.item_code
		where se.docstatus = 1 and se.purpose = 'Manufacture' and se.work_order = %s
		group by i.item_group""",
		work_order,
		as_dict=True,
	)
	qty = sum(flt(r.fg_qty) for r in rows) or 1
	fg_amount = sum(flt(r.fg_amount) for r in rows)
	fabric = sum(flt(r.amount) for r in rows if r.item_group in ("Finished Fabric", "Fabric") and not r.fg_qty)
	trims = sum(flt(r.amount) for r in rows if r.item_group in CONSUMABLE_ITEM_GROUPS)
	cmt = fg_amount - fabric - trims
	washed_item = item_code.replace("-UW-", "-SW-")
	wash = frappe.db.sql(
		"""select avg(i.service_cost_per_qty), avg(i.rm_cost_per_qty), avg(i.rate) from `tabSubcontracting Receipt Item` i
		join `tabSubcontracting Receipt` p on p.name = i.parent where p.docstatus = 1 and i.item_code = %s""",
		washed_item,
	)[0]
	unwashed = fg_amount / qty
	return frappe._dict(
		work_order=work_order, item_code=item_code, qty=qty, fabric_per_pc=fabric / qty, trims_per_pc=trims / qty,
		cmt_per_pc=cmt / qty, unwashed_per_pc=unwashed, washing_per_pc=flt(wash[0]),
		washed_per_pc=flt(wash[2]) or unwashed + flt(wash[0]),
	)


# ---------------------------------------------------------------- 9.10 WIP snapshot
def inventory_between_processes(filters) -> list[dict]:
	f, company, _from, _to = _period(filters)
	return frappe.db.sql(
		f"""select ifnull(w.parent_warehouse, w.name) as warehouse_group, w.name as warehouse, w.dm_inventory_status,
			b.item_code, i.stock_uom, sum(b.actual_qty) qty, sum(b.stock_value) value
		from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse join `tabItem` i on i.name = b.item_code
		where b.actual_qty != 0 {"and w.company = %(company)s" if company else ""}
		group by w.name, b.item_code order by w.parent_warehouse, w.name, b.item_code""",  # noqa: S608
		{"company": company},
		as_dict=True,
	)


def wip_value(company: str | None = None) -> float:
	return flt(frappe.db.sql(
		f"""select sum(b.stock_value) from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
		where w.dm_inventory_status = 'WIP' {"and w.company = %(company)s" if company else ""}""",  # noqa: S608
		{"company": company},
	)[0][0])
