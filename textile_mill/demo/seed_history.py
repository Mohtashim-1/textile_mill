"""Dashboard history for the demo (Part C §8): 12 months of synthetic KPI snapshots before D0,
sample downtime logs, cost-center budgets and reorder levels. Everything generated here is
flagged ("is_synthetic" or "Sample history") and the whole module is idempotent."""

import math
import random

import frappe
from frappe.utils import add_days, date_diff, flt, get_datetime, getdate, now_datetime, today

from textile_mill.constants import PRODUCTION_STAGES, STAGE_COST_CENTER
from textile_mill.dashboards import kpi as K
from textile_mill.dashboards.common import LEVEL_KPIS, SUM_KPIS
from textile_mill.dashboards.seed import seed_kpis
from textile_mill.demo.run_journey import d0 as get_d0

SEED = 42
HISTORY_DAYS = 365
SAMPLE = "Sample history"

# Used when the demo period has no value to anchor a KPI's history on.
FALLBACK_BASE = {
	"CASH_POSITION": 18_000_000,
	"ORDER_BOOK": 9_000_000,
	"WIP_VALUE": 2_500_000,
	"DOWNTIME_HRS": 6,
	"OTD_PCT": 92,
	"FIRST_PASS_QI": 94,
	"REDYE_PCT": 4,
	"OEE": 68,
}
ANNUAL_DRIFT = {"Higher is better": 0.05, "Lower is better": -0.05}
COST_KPIS = {"COST_PER_UNIT", "COTTON_WASTE_PRICE", "VIRGIN_COTTON_PRICE", "PRICE_REALISATION_FABRIC"}
COST_INFLATION = 0.08

# reason code -> (weight, stages it applies to; None = all)
DOWNTIME_MIX = {
	"MECH-BRK": (30, None),
	"ELEC": (15, None),
	"PM": (15, None),
	"PWR": (10, None),
	"YARN-SHT": (8, ("Indigo Dyeing", "Weaving")),
	"BEAM-CHG": (8, ("Weaving",)),
	"SHADE-HOLD": (8, ("Fiber Dyeing", "Indigo Dyeing")),
	"NO-ORD": (6, None),
}
REORDER = {
	# item: (warehouse, level, reorder qty) — indigo is deliberately set above stock so the alert shows.
	"CHM-IND": ("Chemicals & Dyes Store", 60, 120),
	"CHM-HYD": ("Chemicals & Dyes Store", 40, 150),
	"CHM-CAU": ("Chemicals & Dyes Store", 30, 120),
	"CHM-SIZE": ("Chemicals & Dyes Store", 80, 400),
	"CHM-SBLK": ("Chemicals & Dyes Store", 10, 80),
	"CHM-WET": ("Chemicals & Dyes Store", 5, 20),
	"TRM-THR": ("Trims Store", 15, 100),
	"TRM-ZIP": ("Trims Store", 50, 2000),
}
BUDGET_ACCOUNT_CANDIDATES = ("Utility Expenses", "Salary", "Miscellaneous Expenses")
LOOM_TYPES = ("Air-jet Loom", "Terry Loom", "Flat Wide Loom")


def company() -> str:
	return frappe.db.get_single_value("Global Defaults", "default_company")


def run(rebuild_real: int = 1) -> None:
	random.seed(SEED)
	co = company()
	d0 = get_d0()
	seed_reorder_levels(co)
	seed_budgets(co, d0)
	seed_downtime_logs(co, d0)
	frappe.db.commit()
	n = seed_snapshots(co, d0)
	frappe.db.commit()
	print(f"Synthetic snapshots: {n}")
	if int(rebuild_real):
		from textile_mill.dashboards.snapshot import build_for

		written, day = 0, d0
		while day <= getdate(today()):
			written += build_for(day)
			frappe.db.commit()
			day = add_days(day, 1)
		print(f"Real snapshots {d0} → {today()}: {written}")
	frappe.clear_cache()


# ---------------------------------------------------------------- reorder levels
def seed_reorder_levels(co: str) -> None:
	abbr = frappe.get_cached_value("Company", co, "abbr")
	for item_code, (store, level, qty) in REORDER.items():
		if not frappe.db.exists("Item", item_code):
			continue
		warehouse = f"{store} - {abbr}"
		item = frappe.get_doc("Item", item_code)
		row = next((r for r in item.reorder_levels if r.warehouse == warehouse), None)
		if row and flt(row.warehouse_reorder_level) == level and flt(row.warehouse_reorder_qty) == qty:
			continue
		if not row:
			row = item.append("reorder_levels", {"warehouse": warehouse, "material_request_type": "Purchase"})
		row.warehouse_reorder_level = level
		row.warehouse_reorder_qty = qty
		item.save(ignore_permissions=True)


# ---------------------------------------------------------------- budgets
def _budget_account(co: str) -> str | None:
	for name in BUDGET_ACCOUNT_CANDIDATES:
		account = frappe.db.get_value("Account", {"account_name": name, "company": co, "is_group": 0})
		if account:
			return account
	return frappe.db.get_value("Account", {"root_type": "Expense", "company": co, "is_group": 0, "account_type": ""})


def seed_budgets(co: str, d0) -> None:
	fiscal_year = frappe.db.get_value("Fiscal Year", {"year_start_date": ["<=", d0], "year_end_date": [">=", d0]})
	account = _budget_account(co)
	if not (fiscal_year and account):
		print("Budgets skipped: no fiscal year or expense account")
		return
	abbr = frappe.get_cached_value("Company", co, "abbr")
	rng = random.Random(SEED)
	days = max(date_diff(today(), d0) + 1, 1)
	absorbed = dict(frappe.db.sql(
		"""select gle.cost_center, sum(gle.credit - gle.debit) from `tabGL Entry` gle join `tabAccount` a on a.name = gle.account
		where gle.is_cancelled = 0 and gle.company = %s and a.root_type = 'Expense' and gle.posting_date >= %s
		and (a.account_type = 'Expenses Included In Valuation' or a.name in (select distinct expense_account
			from `tabLanded Cost Taxes and Charges` where parenttype = 'Stock Entry')) group by gle.cost_center""",
		(co, d0),
	))
	for center in dict.fromkeys(STAGE_COST_CENTER.values()):
		cost_center = f"{center} - {abbr}"
		if not frappe.db.exists("Cost Center", cost_center):
			continue
		run_rate = flt(absorbed.get(cost_center)) / days * 365
		# ±12% around the run rate so some cost centers land over budget.
		amount = round(max(run_rate, 500_000) * (1 + rng.uniform(-0.12, 0.12)), -4)
		name = frappe.db.get_value("Budget", {"cost_center": cost_center, "fiscal_year": fiscal_year, "docstatus": 1})
		if name:
			continue
		frappe.get_doc({
			"doctype": "Budget",
			"budget_against": "Cost Center",
			"company": co,
			"cost_center": cost_center,
			"fiscal_year": fiscal_year,
			"applicable_on_booking_actual_expenses": 1,
			"action_if_annual_budget_exceeded": "Warn",
			"action_if_accumulated_monthly_budget_exceeded": "Ignore",
			"accounts": [{"account": account, "budget_amount": amount}],
		}).insert(ignore_permissions=True).submit()


# ---------------------------------------------------------------- downtime logs
def seed_downtime_logs(co: str, d0) -> None:
	frappe.db.delete("Machine Downtime Log", {"remarks": SAMPLE})
	seed_kpis()
	rng = random.Random(SEED + 1)
	# Looms already report stops on their shift logs, so only other machines get sample logs,
	# and only on days they actually ran (a job-card time log that day).
	workstations = {w.name: w for w in K.stage_workstations(PRODUCTION_STAGES) if w.workstation_type not in LOOM_TYPES}
	ran = frappe.db.sql(
		"""select distinct jc.workstation, date(tl.from_time) d from `tabJob Card Time Log` tl join `tabJob Card` jc on jc.name = tl.parent
		where jc.docstatus = 1 and jc.company = %s and date(tl.from_time) between %s and %s order by d, jc.workstation""",
		(co, d0, today()),
	)
	for name, day in ran:
		w = workstations.get(name)
		if not w or rng.random() > 0.45:
			continue
		reasons = [(c, wt) for c, (wt, stages) in DOWNTIME_MIX.items() if stages is None or w.dm_stage in stages]
		reason = rng.choices([c for c, _w in reasons], weights=[wt for _c, wt in reasons])[0]
		start = get_datetime(f"{day} 07:00:00").replace(hour=rng.randint(7, 19), minute=rng.choice((0, 15, 30, 45)))
		minutes = 90 if reason == "PM" else rng.choice((15, 20, 30, 45, 60))
		doc = frappe.get_doc({
			"doctype": "Machine Downtime Log",
			"posting_date": day,
			"workstation": w.name,
			"from_time": start,
			"to_time": frappe.utils.add_to_date(start, minutes=minutes),
			"reason": reason,
			"remarks": SAMPLE,
		})
		doc.insert(ignore_permissions=True)
		doc.submit()


# ---------------------------------------------------------------- synthetic snapshots
def _bases(co: str, d0) -> dict[tuple, float]:
	ctx = frappe._dict(company=co, from_date=getdate(d0), to_date=getdate(today()), stage=None, stages=None, plant=None)
	days = max(date_diff(today(), d0) + 1, 1)
	out = {}
	for code, stage in K.SNAPSHOT_KPIS:
		value = K.calculate(code, frappe._dict(ctx, stage=stage), stage)["value"]
		if code in SUM_KPIS and value is not None:
			value = flt(value) / days * 7 / 6
		if not value:
			value = FALLBACK_BASE.get(code)
		if value:
			out[(code, stage)] = flt(value)
	return out


def seed_snapshots(co: str, d0) -> int:
	frappe.db.delete("KPI Daily Snapshot", {"is_synthetic": 1})
	rng = random.Random(SEED)
	bases = _bases(co, d0)
	start = add_days(d0, -HISTORY_DAYS)
	now = now_datetime()
	fields = ["name", "creation", "modified", "owner", "modified_by", "docstatus", "idx", "snapshot_date", "kpi", "stage",
		"value", "numerator", "denominator", "is_synthetic"]
	rows = []
	for (code, stage), base in sorted(bases.items(), key=lambda x: (x[0][0], x[0][1] or "")):
		if not frappe.db.exists("KPI Definition", code):
			continue
		direction = frappe.get_cached_value("KPI Definition", code, "direction") or "Higher is better"
		unit = frappe.get_cached_value("KPI Definition", code, "unit")
		for i in range(HISTORY_DAYS):
			day = add_days(start, i)
			years_back = (HISTORY_DAYS - i) / 365
			if code in COST_KPIS:
				trend = 1 - COST_INFLATION * years_back
			else:
				trend = 1 - ANNUAL_DRIFT.get(direction, 0) * years_back
			season = 1 + 0.03 * math.sin(2 * math.pi * (day.timetuple().tm_yday / 365))
			if code in SUM_KPIS:
				if day.weekday() == 6:
					continue
				noise = rng.gauss(1, 0.25)
			elif code in LEVEL_KPIS:
				noise = rng.gauss(1, 0.03)
			else:
				noise = rng.gauss(1, 0.04)
			value = base * trend * season * max(noise, 0.2)
			if unit == "%":
				value = min(value, 100)
			rows.append((frappe.generate_hash(length=10), now, now, "Administrator", "Administrator", 0, 0, day, code, stage or "",
				round(value, 4), 0, 0, 1))
	frappe.db.bulk_insert("KPI Daily Snapshot", fields, rows)
	return len(rows)
