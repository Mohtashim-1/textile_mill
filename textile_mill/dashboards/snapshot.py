"""KPI Daily Snapshot builder (Part C §5.3)."""

import frappe
from frappe.utils import add_days, date_diff, getdate, today

MAX_REBUILD_DAYS = 400


def build_yesterday() -> None:
	build_for(add_days(today(), -1))


def build_for(date) -> int:
	from textile_mill.dashboards.kpi import snapshot_all

	return snapshot_all(date)


@frappe.whitelist()
def rebuild(from_date, to_date) -> int:
	"""Backfill real snapshots for a date range (System Manager / Plant Controller)."""
	frappe.only_for(("System Manager", "Plant Controller"))
	start, end = getdate(from_date), getdate(to_date)
	if date_diff(end, start) > MAX_REBUILD_DAYS:
		frappe.throw(frappe._("Rebuild at most {0} days at a time.").format(MAX_REBUILD_DAYS))
	written, day = 0, start
	while day <= end:
		written += build_for(day)
		day = add_days(day, 1)
	return written
