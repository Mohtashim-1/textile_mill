"""Knitting queries (Part E §E5–E8), shared by dashboard KPIs and stage panels."""

import frappe
from frappe.utils import flt

from textile_mill.reports_lib import _period

FABRIC_TESTS = ("Shrinkage %", "Spirality %")


def knitting_rows(filters) -> list[dict]:
	f, _company, from_date, to_date = _period(filters)
	conditions = ["p.docstatus = 1", "p.posting_date between %(from)s and %(to)s"]
	values = {"from": from_date, "to": to_date}
	for key, column in (("shift", "p.shift"), ("machine", "r.machine"), ("work_order", "p.work_order")):
		if f.get(key):
			conditions.append(f"{column} = %({key})s")
			values[key] = f.get(key)
	return frappe.db.sql(
		f"""select p.name as knitting_shift_production, p.posting_date, p.shift, p.work_order, r.machine, r.operator,
			r.dia_inch, r.gauge, r.stitch_length_mm, r.rpm, r.efficiency_pct, r.rolls_produced, r.kg_produced as kg,
			r.defects_count, r.stop_minutes
		from `tabKnitting Machine Row` r join `tabKnitting Shift Production` p on p.name = r.parent
		where {" and ".join(conditions)}
		order by p.posting_date, p.shift, r.idx""",  # noqa: S608
		values,
		as_dict=True,
	)


def knit_efficiency(filters) -> float | None:
	rows = knitting_rows(filters)
	total = sum(flt(r.kg) for r in rows)
	return sum(flt(r.efficiency_pct) * flt(r.kg) for r in rows) / total if total else None


def defects_per_roll(filters) -> float | None:
	rows = knitting_rows(filters)
	rolls = sum(flt(r.rolls_produced) for r in rows)
	return sum(flt(r.defects_count) for r in rows) / rolls if rolls else None


def dye_batches(filters) -> list[dict]:
	"""Knit dyeing work orders started in the period with their jet load (WO qty ÷ batch capacity)."""
	_f, company, from_date, to_date = _period(filters)
	return frappe.db.sql(
		"""select name as work_order, production_item, qty, produced_qty, machine_load_pct, dye_recipe, status,
			date(planned_start_date) as start_date
		from `tabWork Order` where docstatus = 1 and dm_stage = 'Knit Dyeing' and status != 'Stopped'
		and date(planned_start_date) between %(from)s and %(to)s and (%(company)s is null or company = %(company)s)
		order by planned_start_date""",
		{"from": from_date, "to": to_date, "company": company},
		as_dict=True,
	)


def dye_machine_load_pct(filters) -> float | None:
	rows = dye_batches(filters)
	return sum(flt(r.machine_load_pct) for r in rows) / len(rows) if rows else None


def fabric_tests(filters) -> list[dict]:
	"""Shrinkage / spirality readings on finished knit QIs in the period."""
	_f, _company, from_date, to_date = _period(filters)
	return frappe.db.sql(
		"""select qi.name, qi.report_date, qi.item_code, qi.batch_no, r.specification, r.reading_1 as value, r.status
		from `tabQuality Inspection Reading` r join `tabQuality Inspection` qi on qi.name = r.parent
		join `tabItem` i on i.name = qi.item_code
		where qi.docstatus = 1 and i.dm_stage = 'Knit Finishing' and r.specification in %(tests)s
		and qi.report_date between %(from)s and %(to)s order by qi.report_date, qi.name""",
		{"from": from_date, "to": to_date, "tests": FABRIC_TESTS},
		as_dict=True,
	)


def shrinkage_spirality_pass_pct(filters) -> float | None:
	rows = fabric_tests(filters)
	return sum(r.status == "Accepted" for r in rows) / len(rows) * 100 if rows else None
