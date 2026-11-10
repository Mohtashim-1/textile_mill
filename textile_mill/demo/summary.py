"""Console summary of the denim demo (Part B §11.8)."""

import frappe
from frappe.utils import flt, fmt_money

from textile_mill import reports_lib as rl
from textile_mill.constants import DENIM_STAGES
from textile_mill.demo import data


def _pct(value) -> str:
	return "  n/a" if value is None else f"{value:5.1f}%"


def print_summary(company: str, from_date, to_date) -> dict:
	filters = {"company": company, "from_date": from_date, "to_date": to_date}
	yields = {r.stage: r for r in rl.stage_yield_summary(filters)}
	costs = {r.stage: r for r in rl.cost_per_unit_by_stage(filters)}

	print(f"\n{'STAGE':<16}{'OUTPUT':>14}  {'YIELD':>6}  {'WASTE':>6}  {'COST/UNIT(ACT)':>16}  {'COST/UNIT(STD)':>16}  {'VAR%':>6}")
	for stage in DENIM_STAGES:
		y, c = yields.get(stage), costs.get(stage)
		if not y:
			continue
		output = f"{y.output_qty:,.0f} {y.output_uom}"
		yld = _pct(y.yield_pct) if y.same_uom else f"{y.output_per_input:.3f}/u"
		print(
			f"{stage:<16}{output:>14}  {yld:>6}  {_pct(y.waste_pct):>6}  "
			f"{'PKR ' + format(c.actual_per_unit, ',.2f'):>16}  {'PKR ' + format(c.standard_per_unit, ',.2f'):>16}  {_pct(c.variance_pct):>6}"
		)

	recipes = [r for r in rl.recipe_variance(filters) if not r.get("is_total")]
	indigo = next((r for r in recipes if r.item_code == "CHM-IND"), None)
	sblk = next((r for r in recipes if r.item_code == "CHM-SBLK"), None)
	if indigo:
		print(f"Indigo: {indigo.actual_g_per_kg:.1f} g/kg actual vs recipe {indigo.recipe_g_per_kg:.1f} ({_pct(indigo.variance_pct).strip()})")
	if sblk:
		print(f"Sulphur black variance: {_pct(sblk.variance_pct).strip()}")

	weaving = yields.get("Weaving")
	print(f"Grey fabric per kg yarn: {weaving.output_per_input:.3f} m/kg" if weaving else "Grey fabric: n/a")
	print(f"Avg loom efficiency: {rl.weighted_loom_efficiency({**filters, 'loom_type': 'Air-jet Denim'}):.1f}%")

	g = rl.grade_split(filters)
	print(f"Fabric grades: A {g['A_pct']:.1f}% | B {g['B_pct']:.1f}% | R {g['Rejected_pct']:.1f}%")

	cut = frappe.db.get_value("Cut Plan", {"company": company, "docstatus": 1, "style_template": "JNS-SLIM-UW"},
		["cutting_variance_m", "cutting_variance_pct", "total_pieces"], as_dict=True, order_by="creation desc")
	if cut:
		print(f"Cutting variance: {cut.cutting_variance_m:.1f} m ({cut.cutting_variance_pct:.1f}%) on {cut.total_pieces:,} pcs")

	corrective = sum(flt(r.cost) for r in rl.corrective_jobs(filters))
	print(f"Corrective cost: PKR {corrective:,.0f}")

	so_jns = frappe.db.get_value("Sales Order", {"po_no": data.SO_JNS["po_no"], "docstatus": 1})
	if so_jns:
		p = rl.order_profitability(so_jns)
		print(f"Jeans SO margin: {fmt_money(p.gross_margin, currency='PKR')} ({p.margin_pct:.1f}%)")

	check = genealogy_check()
	print(check["line"])
	return {"yields": yields, "costs": costs, "grades": g, "genealogy_ok": check["ok"]}


def genealogy_check() -> dict:
	dn = frappe.db.get_value(
		"Delivery Note Item", {"item_code": ["like", "JNS-SLIM-SW-%"], "docstatus": 1}, ["parent", "item_code"], as_dict=True
	)
	if not dn:
		return {"ok": False, "line": "Genealogy check: no jeans delivery yet"}
	rows = rl.genealogy({"delivery_note": dn.parent, "max_depth": 15})
	by_name = {r.name: r for r in rows}
	leaf = next((r for r in rows if r.node_type == "Supplier" and r.parent_node
		and (by_name[r.parent_node].item_code or "").startswith("CW-")), None)
	if not leaf:
		return {"ok": False, "line": f"Genealogy check: {dn.item_code} ← cotton waste lot NOT FOUND"}
	chain, node = [], by_name[leaf.parent_node]
	while node and node.parent_node:
		chain.append(node.batch_no or node.voucher_no or node.item_code)
		node = by_name.get(node.parent_node)
	path = " ← ".join([dn.item_code, *reversed(chain)])
	return {"ok": True, "line": f"Genealogy check: {path} ({leaf.party})  OK"}
