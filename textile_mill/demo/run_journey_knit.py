"""Knitting demo journey (Part E §E7, steps K-01…K-08). Idempotent; posting dates strictly increase.

5,000 navy crew-neck T-shirts (S:M:L:XL = 1:2:2:1) for a domestic retailer:
knit 1,250 kg greige → dye 1,190 kg → finish 1,165 kg → cut plan in kg → stitch → deliver.
    bench --site <site> execute textile_mill.demo.run_journey_knit.run_all
"""

import frappe
from frappe.utils import flt, today

from textile_mill.demo import data_knit as K
from textile_mill.demo.run_journey import company, day, log, make_delivery, make_invoice, make_qi, make_so, make_wo, produce, tag, tagged
from textile_mill.demo.run_journey_ht import ht_transfer, process_reposts, transfer_rows
from textile_mill.manufacturing import make_material_entry, new_batch
from textile_mill.setup.masters_knit import KNITTERS
from textile_mill.utils import wh

PLANT = "Plant-5 Knitting"


def kd(n: int) -> int:
	"""Knit day n as a denim-day offset."""
	return K.K_OFFSET + n


def kt(n: int | str) -> str:
	return f"K-{n:02d}" if isinstance(n, int) else f"K-{n}"


def so_name() -> str | None:
	return frappe.db.get_value("Sales Order", {"po_no": K.SO_TSH["po_no"], "docstatus": 1})


# ---------------------------------------------------------------- steps
def step_01_opening_and_order():
	step = kt(1)
	if not tagged("Stock Entry", step):
		rows = []
		for store, items in K.OPENING_STOCK.items():
			for item, qty in items:
				batch = new_batch(item, manufacturing_date=day(kd(0)), dm_stage="Raw") if frappe.get_cached_value(
					"Item", item, "has_batch_no") else None
				rows.append({"item_code": item, "qty": qty, "t_warehouse": wh(store), "batch_no": batch,
					"basic_rate": frappe.db.get_value("Item", item, "valuation_rate")})
		se = make_material_entry("Material Receipt", company(), rows, day(kd(0)), "07:40:00",
			remarks=f"{tag(step)} Knitting opening stock", plant=PLANT)
		log(f"K-01 opening stock {se.name}")
	if not tagged("Purchase Receipt", step):
		p = K.VC_PURCHASE
		batch = new_batch(p["item"], manufacturing_date=day(kd(0)), dm_stage="Raw")
		pr = frappe.get_doc({
			"doctype": "Purchase Receipt", "company": company(), "supplier": p["supplier"], "set_posting_time": 1,
			"posting_date": day(kd(0)), "posting_time": "09:40:00", "buying_price_list": "Standard Buying",
			"remarks": f"{tag(step)} virgin cotton for knitting yarn", "plant": PLANT,
			"items": [{"item_code": p["item"], "qty": p["qty"], "rate": p["rate"], "warehouse": wh(p["warehouse"]),
				"batch_no": batch, "use_serial_batch_fields": 1}],
		})
		pr.flags.ignore_permissions = True
		pr.insert()
		qi = make_qi(p["item"], "Purchase Receipt", pr.name, p["qi"], "Incoming", day(kd(0)), batch, pr.items[0].name,
			remarks=f"{tag(step)} incoming", sample_size=10)
		pr.reload()
		pr.items[0].quality_inspection = qi.name
		pr.save()
		pr.submit()
		log(f"K-01 purchase {pr.name}: {p['qty']} {p['item']}")
	log(f"K-01 sales order {make_so(K.SO_TSH, kt(1), kd(0))}")


def step_02_spinning():
	item, qty = K.SPINNING
	wo = make_wo(item, qty, "Spinning", kt(2), kd(1), stores=K.STORES["Spinning"])
	ht_transfer(wo, kt(2), kd(1), "08:30:00",
		transfer_rows([("VC-RAW", flt(qty * K.YARN_PER_KG, 2))], "Virgin Cotton Store", batched=True))
	produce(wo, qty, kt(2), kd(1), "21:30:00", None, "OP-SP-01", {"dm_beam_nos": ""})
	log(f"K-02 knitting yarn spun: {qty} kg {item}")


def knit_shift(wo: str, shift: str, n_day: int, time: str, rows: list[dict]):
	existing = frappe.db.get_value("Knitting Shift Production",
		{"work_order": wo, "shift": shift, "posting_date": day(n_day), "docstatus": 1})
	if existing:
		return frappe.get_doc("Knitting Shift Production", existing)
	ksp = frappe.get_doc({
		"doctype": "Knitting Shift Production", "posting_date": day(n_day), "posting_time": time, "shift": shift,
		"work_order": wo, "supervisor": KNITTERS[0], "machines": rows,
	})
	ksp.flags.ignore_permissions = True
	ksp.insert()
	ksp.submit()
	return ksp


def step_03_knitting():
	k = K.KNITTING
	wo = make_wo("GK-SJ-160", k["qty"], "Knitting", kt(3), kd(2), stores=K.STORES["Knitting"])
	ht_transfer(wo, kt(3), kd(2), "06:30:00", transfer_rows([("YRN-K-30NE-CT", k["yarn_kg"])], "Knit Yarn Store", batched=True))
	for i, (shift, n, time, kg) in enumerate(k["shifts"]):
		ksp = knit_shift(wo, shift, kd(n), time, K.knit_rows(k["machines"], kg, 300 + i, KNITTERS))
		log(f"K-03 knitting shift {ksp.name} ({shift}): {ksp.total_kg} kg, {ksp.total_rolls} rolls @ {ksp.avg_efficiency_pct}% "
			f"→ {ksp.greige_batch}")
	log(f"K-03 knitting WO {wo}: {frappe.db.get_value('Work Order', wo, 'status')}")


def step_04_knit_dyeing():
	d = K.DYEING
	for i, (qty, greige) in enumerate(d["batches"]):
		step = kt(f"04-{i}")
		wo = make_wo("DK-SJ-160-NAVY", qty, "Knit Dyeing", step, kd(3), dye_recipe=d["recipe"], stores=K.STORES["Knit Dyeing"])
		rows = transfer_rows([("GK-SJ-160", greige)], "Greige Knit Store", batched=True)
		rows += transfer_rows([(c, flt(greige * per_kg, 3)) for c, per_kg in d["chemicals_per_kg"]], "Chemicals & Dyes Store")
		ht_transfer(wo, step, kd(3), f"0{8 + i}:00:00", rows)
		produce(wo, qty, step, kd(3), f"{18 + 2 * i}:00:00", None, d["operator"])
		log(f"K-04 jet batch {wo}: {qty} kg dyed from {greige} kg greige, machine load "
			f"{frappe.db.get_value('Work Order', wo, 'machine_load_pct')}%")


def step_05_finishing():
	f = K.FINISHING
	wo = make_wo("FK-SJ-160-NAVY", f["qty"], "Knit Finishing", kt(5), kd(4), stores=K.STORES["Knit Finishing"])
	rows = transfer_rows([("DK-SJ-160-NAVY", f["dyed_kg"])], "Dyed Knit Store", batched=True)
	rows += transfer_rows([("CHM-SOFT", f["softener"])], "Chemicals & Dyes Store")
	ht_transfer(wo, kt(5), kd(4), "07:30:00", rows)
	produce(wo, f["qty"], kt(5), kd(4), "20:00:00", f["qi"], f["operator"], {"dm_gsm": f["qi"]["GSM"]})
	log(f"K-05 finished knit {f['qty']} kg (stenter + compactor), QI shrinkage {f['qi']['Shrinkage %']}% "
		f"spirality {f['qi']['Spirality %']}%")


def step_06_cut_plan():
	so = so_name()
	if frappe.db.exists("Cut Plan", {"sales_order": so, "docstatus": 1}):
		return
	c = K.CUT_PLAN
	cp = frappe.get_doc({
		"doctype": "Cut Plan", "company": company(), "posting_date": day(kd(5)), "sales_order": so,
		"style_template": K.TSHIRT, "fabric_item": "FK-SJ-160-NAVY", "marker_length_m": c["marker_length_m"],
		"plies": c["plies"], "end_bit_allowance_pct": c["end_bit_allowance_pct"],
		"size_ratio": [{"size": s, "ratio": r} for s, r in c["ratio"]],
	})
	cp.flags.ignore_permissions = True
	cp.insert()
	cp.allocate_rolls()
	cp.reload()
	cp.submit()
	bundles = frappe.db.count("Bundle Ticket", {"cut_plan": cp.name})
	log(f"K-06 cut plan {cp.name}: {cp.total_pieces} pcs, marker {cp.marker_qty_per_ply():.3f} kg/ply, issued "
		f"{cp.fabric_issued_m} kg vs standard {cp.standard_fabric_m} kg ({cp.cutting_variance_pct}%), {bundles} bundles")


def step_07_stitching():
	from textile_mill.textile_mill.doctype.bundle_ticket.bundle_ticket import complete_work_order, set_status

	cp = frappe.db.get_value("Cut Plan", {"sales_order": so_name(), "docstatus": 1})
	bundles = frappe.get_all("Bundle Ticket", filters={"cut_plan": cp}, fields=["name", "status"], order_by="name asc")
	for i, b in enumerate(bundles):
		if b.status in ("Cut", "In Stitching"):
			line = K.STITCH_LINES[i % len(K.STITCH_LINES)]
			set_status(b.name, "In Stitching", line)
			set_status(b.name, "Stitched", line, f"{day(kd(6 if i < len(bundles) / 2 else 7))} 16:00:00")
	for k, wo in enumerate(frappe.get_all("Work Order", filters={"cut_plan": cp, "docstatus": 1}, pluck="name", order_by="name asc")):
		if frappe.db.get_value("Work Order", wo, "status") != "Completed":
			complete_work_order(wo, str(day(kd(7))), f"1{7 + k}:00:00")
	log(f"K-07 stitched {len(bundles)} bundles; T-shirt work orders completed")


def step_08_delivery():
	step = kt(8)
	rows = [{"item_code": item, "qty": qty, "warehouse": wh("Knit FG Store")} for item, qty, _rate in K.SO_TSH["items"]]
	dn = make_delivery(so_name(), step, kd(8), "11:30:00", rows)
	si = make_invoice(dn, step, kd(8), PLANT)
	log(f"K-08 delivered {dn} ({sum(r['qty'] for r in rows)} T-shirts), invoiced {si}")


STEPS = [step_01_opening_and_order, step_02_spinning, step_03_knitting, step_04_knit_dyeing, step_05_finishing,
	step_06_cut_plan, step_07_stitching, step_08_delivery]


def run_all(upto: int | None = None) -> None:
	"""Run every knitting step in order (optionally only the first `upto`). Commits after each step."""
	frappe.flags.mute_emails = True
	log(f"Knitting demo journey: K-01 = {day(kd(0))} (today {today()})")
	for i, fn in enumerate(STEPS, start=1):
		if upto and i > int(upto):
			break
		fn()
		frappe.db.commit()
	process_reposts()
	frappe.db.commit()
