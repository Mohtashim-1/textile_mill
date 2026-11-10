"""Home Textile demo journey (Part D §D7, steps HT-01…HT-16). Idempotent; posting dates strictly increase.

Runs after the denim journey on the same D0 (HT-01 = D0 + HT_OFFSET days):
    bench --site <site> execute textile_mill.demo.run_journey_ht.run_all
Every document carries a `[DEMO-HT-NN]` tag and each step skips itself when its output already exists.
"""

import frappe
from frappe.utils import flt, today

from textile_mill.demo import data_ht as H
from textile_mill.demo.run_journey import (
	company,
	day,
	log,
	make_invoice,
	make_qi,
	make_so,
	make_wo,
	produce,
	tag,
	tagged,
)
from textile_mill.manufacturing import make_material_entry, make_transfer_entry, new_batch, pick_batches
from textile_mill.utils import wh

PLANT = "Plant-4 Home Textile"


def hd(n: int) -> int:
	"""HT day n as a denim-day offset (what `day()` and the shared helpers expect)."""
	return H.HT_OFFSET + n


def ht(n: int | str) -> str:
	return f"HT-{n:02d}" if isinstance(n, int) else f"HT-{n}"


def so_name(spec: dict) -> str | None:
	return frappe.db.get_value("Sales Order", {"po_no": spec["po_no"], "docstatus": 1})


def transfer_rows(items: list[tuple[str, float]], store: str, batched: bool = False) -> list[dict]:
	rows = []
	for item, qty in items:
		if batched:
			rows += [{"item_code": item, "qty": q, "s_warehouse": wh(store), "batch_no": b} for b, q in pick_batches(item, wh(store), qty)]
		else:
			rows.append({"item_code": item, "qty": qty, "s_warehouse": wh(store)})
	return rows


def ht_transfer(wo: str, step: str, n_day: int, time: str, rows: list[dict]) -> None:
	trf = f"{step}-TRF"
	if tagged("Stock Entry", trf, extra={"work_order": wo}):
		return
	se = make_transfer_entry(wo, rows, day(n_day), time, remarks=f"{tag(trf)} transfer")
	log(f"  Transfer {se.name} → {wo}")


def close_wo(wo: str) -> None:
	from erpnext.manufacturing.doctype.work_order.work_order import close_work_order

	if frappe.db.get_value("Work Order", wo, "status") not in ("Completed", "Closed"):
		close_work_order(wo, "Closed")


# ---------------------------------------------------------------- steps
def step_01_opening_stock():
	step = ht(1)
	if not tagged("Stock Entry", step):
		rows = []
		for store, items in H.OPENING_STOCK.items():
			for item, qty in items:
				batch = new_batch(item, manufacturing_date=day(hd(0)), dm_stage="Raw") if frappe.get_cached_value(
					"Item", item, "has_batch_no") else None
				rows.append({"item_code": item, "qty": qty, "t_warehouse": wh(store), "batch_no": batch,
					"basic_rate": frappe.db.get_value("Item", item, "valuation_rate")})
		se = make_material_entry("Material Receipt", company(), rows, day(hd(0)), "07:30:00",
			remarks=f"{tag(step)} Home Textile opening stock", plant=PLANT)
		log(f"HT-01 opening stock {se.name}")
	if not tagged("Purchase Receipt", step):
		p = H.VC_PURCHASE
		batch = new_batch(p["item"], manufacturing_date=day(hd(0)), dm_stage="Raw")
		pr = frappe.get_doc({
			"doctype": "Purchase Receipt", "company": company(), "supplier": p["supplier"], "set_posting_time": 1,
			"posting_date": day(hd(0)), "posting_time": "09:30:00", "buying_price_list": "Standard Buying",
			"remarks": f"{tag(step)} virgin cotton for home textile", "plant": PLANT,
			"items": [{"item_code": p["item"], "qty": p["qty"], "rate": p["rate"], "warehouse": wh(p["warehouse"]),
				"batch_no": batch, "use_serial_batch_fields": 1}],
		})
		pr.flags.ignore_permissions = True
		pr.insert()
		qi = make_qi(p["item"], "Purchase Receipt", pr.name, p["qi"], "Incoming", day(hd(0)), batch, pr.items[0].name,
			remarks=f"{tag(step)} incoming", sample_size=10)
		pr.reload()
		pr.items[0].quality_inspection = qi.name
		pr.save()
		pr.submit()
		log(f"HT-01 purchase {pr.name}: {p['qty']} {p['item']}")


def step_02_sales_orders():
	twl, bed = make_so(H.SO_TWL, ht(2), hd(0)), make_so(H.SO_BED, ht(2), hd(0))
	log(f"HT-02 sales orders {twl}, {bed}")


def step_03_spinning():
	for i, (item, qty) in enumerate(H.SPINNING):
		wo = make_wo(item, qty, "Spinning", ht(3), hd(1), stores=H.STORES["Spinning"])
		ht_transfer(wo, f"03-{i}", hd(1), f"08:{10 * i:02d}:00",
			transfer_rows([("VC-RAW", flt(qty * H.YARN_PER_KG, 2))], "Virgin Cotton Store", batched=True))
		produce(wo, qty, ht(f"03-{i}"), hd(1), f"{18 + i}:30:00", None, H.SPIN_OPERATOR, {"dm_beam_nos": ""})
	log("HT-03 spinning done (ground, pile, weft, sheeting yarn)")


def loom_shift(wo: str, loom_type: str, shift: str, n_day: int, time: str, rows: list[dict], extra: dict | None = None):
	existing = frappe.db.get_value("Loom Shift Production", {"work_order": wo, "shift": shift, "docstatus": 1})
	if existing:
		return frappe.get_doc("Loom Shift Production", existing)
	lsp = frappe.get_doc({
		"doctype": "Loom Shift Production", "posting_date": day(n_day), "posting_time": time, "shift": shift,
		"work_order": wo, "supervisor": "WEAVER-01", "loom_type": loom_type, "looms": rows, **(extra or {}),
	})
	lsp.flags.ignore_permissions = True
	lsp.insert()
	lsp.submit()
	return lsp


def inspect_draft_manufacture(se_name: str, readings: dict, n_day: int, step: str) -> None:
	se = frappe.get_doc("Stock Entry", se_name)
	if se.docstatus == 1:
		return
	fg = next(r for r in se.items if r.is_finished_item)
	template = frappe.db.get_value("BOM", se.bom_no, "quality_inspection_template")
	qi = make_qi(fg.item_code, "Stock Entry", se.name, readings, "In Process", day(n_day), fg.batch_no, fg.name, template,
		f"{tag(step)} grey terry inspection")
	se.reload()
	next(r for r in se.items if r.is_finished_item).quality_inspection = qi.name
	se.save()
	se.submit()
	log(f"  QI {qi.name} {qi.status}; manufacture {se.name} submitted")


def step_04_terry_weaving():
	t = H.TERRY
	wo = make_wo("GT-500", t["qty"], "Terry Weaving", ht(4), hd(2), stores=H.STORES["Terry Weaving"])
	ht_transfer(wo, "04", hd(2), "06:00:00", transfer_rows(t["transfer"], "HT Yarn Store", batched=True))
	weavers = [f"WEAVER-{i:02d}" for i in range(1, 9)]
	for i, shift in enumerate(t["shifts"]):
		rows = H.loom_rows(t["looms"], t["kg_per_shift"], "kg", 100 + i, weavers)
		lsp = loom_shift(wo, "Terry", shift, hd(2), ("15:00:00", "23:00:00")[i], rows,
			{"pile_height_mm": t["pile_height_mm"], "avg_weight_gsm": t["gsm"]})
		log(f"HT-04 terry loom shift {lsp.name}: {lsp.total_kg} kg @ {lsp.avg_efficiency_pct}% → {lsp.grey_batch}")
		# HT-05: grey terry QI releases the draft manufacture entry
		inspect_draft_manufacture(lsp.stock_entry, t["qi"], hd(2), ht(5))
	log(f"HT-05 grey terry inspected; WO status {frappe.db.get_value('Work Order', wo, 'status')}")


def step_06_processing():
	p = H.PROCESSING
	wo = make_wo("PT-500-WHT", p["qty"], "Processing", ht(6), hd(3), dye_recipe=p["recipe"], stores=H.STORES["Processing"])
	rows = transfer_rows([("GT-500", p["grey_kg"])], "Grey Terry Store", batched=True)
	rows += transfer_rows(p["chemicals"], "Chemicals & Dyes Store")
	ht_transfer(wo, "06", hd(3), "07:00:00", rows)
	produce(wo, p["qty"], ht(6), hd(3), "22:00:00", p["qi"], p["operator"], {"dm_gsm": 506})
	log("HT-06 processing done (H2O2 +4% over recipe)")


def step_07_flat_weaving():
	f = H.FLAT
	wo = make_wo("GS-200TC", f["qty"], "Flat Weaving", ht(7), hd(4), stores=H.STORES["Flat Weaving"])
	ht_transfer(wo, "07", hd(4), "06:00:00", transfer_rows(f["transfer"], "HT Yarn Store", batched=True))
	weavers = [f"WEAVER-{i:02d}" for i in range(1, 9)]
	for i, shift in enumerate(f["shifts"]):
		rows = H.loom_rows(f["looms"], f["m_per_shift"], "meters", 200 + i, weavers)
		lsp = loom_shift(wo, "Flat Wide", shift, hd(4), ("15:00:00", "23:00:00")[i], rows)
		log(f"HT-07 flat loom shift {lsp.name}: {lsp.total_meters} m @ {lsp.avg_efficiency_pct}%")


def step_08_printing():
	p = H.PRINTING
	wo = make_wo("PS-200TC-PRT", p["qty"], "Printing", ht(8), hd(5), dye_recipe=p["recipe"], stores=H.STORES["Printing"])
	rows = transfer_rows([("GS-200TC", p["grey_m"])], "Grey Sheeting Store", batched=True)
	rows += transfer_rows(p["chemicals"], "Chemicals & Dyes Store")
	ht_transfer(wo, "08", hd(5), "07:00:00", rows)
	produce(wo, p["qty"], ht(8), hd(5), "20:00:00", p["qi"], "OP-FD-01", {"dm_width_inch": 110})
	log("HT-08 printing done")


def step_09_ctp_orders():
	for item in H.TOWEL_CTP:
		make_wo(item, H.CTP_WO_QTY, "Cut-to-Piece", ht(9), hd(6), stores=H.STORES["Towel CTP"])
	for item, spec in H.SHEET_CTP.items():
		make_wo(item, spec[0], "Cut-to-Piece", ht(9), hd(6), stores=H.STORES["Sheet CTP"])
	log("HT-09 cut-to-piece work orders created")


def step_10_weight_checks():
	for i, (item, spec) in enumerate(H.TOWEL_CTP.items()):
		if frappe.db.exists("Piece Weight Check", {"item_code": item, "docstatus": 1}):
			continue
		pwc = frappe.get_doc({
			"doctype": "Piece Weight Check", "posting_date": day(hd(6)), "item_code": item,
			"work_order": make_wo(item, H.CTP_WO_QTY, "Cut-to-Piece", ht(9), hd(6)),
			"samples": H.weight_samples(spec[1], seed=10 + i),
		})
		pwc.flags.ignore_permissions = True
		pwc.insert()
		pwc.submit()
		log(f"HT-10 weight check {pwc.name} {item}: avg {pwc.avg_weight_kg} kg ({pwc.variance_pct:+}%) → {pwc.result}, "
			f"implied {pwc.implied_gsm} GSM")


def ctp_entry(item: str, wo: str, n_day: int, time: str, issued: float, store: str, cut: int, a: int, seconds: int,
		seconds_kg: float, rags: float, waste: float, line: str, weight_check: str | None) -> None:
	if frappe.db.exists("CTP Production Entry", {"work_order": wo, "docstatus": 1}):
		return
	source = frappe.db.get_value("BOM Item", {"parent": frappe.db.get_value("Work Order", wo, "bom_no"), "idx": 1}, "item_code")
	batches = pick_batches(source, wh(store), issued)
	doc = frappe.get_doc({
		"doctype": "CTP Production Entry", "company": company(), "posting_date": day(n_day), "posting_time": time,
		"shift": "A", "work_order": wo, "line": line, "pieces_cut": cut, "pieces_a": a, "pieces_seconds": seconds,
		"seconds_weight_kg": seconds_kg, "rags_kg": rags, "cutting_waste_kg": waste, "weight_check": weight_check,
		"source_batches": [{"batch_no": b, "warehouse": wh(store), "qty_issued": q} for b, q in batches],
	})
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()
	close_wo(wo)
	log(f"  CTP {doc.name} {item}: planned {doc.pieces_planned}, A {doc.pieces_a}, yield {doc.ctp_yield_pct}%, "
		f"seconds {doc.seconds_pct}% → {doc.stock_entry}")


def step_11_towel_ctp():
	for i, (item, (issued, _avg, cut, a, sec, sec_kg, rags, waste, line)) in enumerate(H.TOWEL_CTP.items()):
		wo = make_wo(item, H.CTP_WO_QTY, "Cut-to-Piece", ht(9), hd(6))
		pwc = frappe.db.get_value("Piece Weight Check", {"item_code": item, "docstatus": 1})
		ctp_entry(item, wo, hd(7), f"{10 + 3 * i}:00:00", issued, "Processed Terry Store", cut, a, sec, sec_kg, rags, waste,
			line, pwc)
	log("HT-11 towel cut-to-piece done")


def step_12_sheet_ctp():
	for i, (item, (qty, issued, cut, a, sec, waste, line)) in enumerate(H.SHEET_CTP.items()):
		wo = make_wo(item, qty, "Cut-to-Piece", ht(9), hd(6))
		ctp_entry(item, wo, hd(8), f"{10 + 4 * i}:00:00", issued, "Processed Sheeting Store", cut, a, sec, 0, 0, waste, line, None)
	log("HT-12 sheet cut-to-piece done")


def step_13_set_assembly():
	for i, (item, spec, stores, piece_store) in enumerate((
		("TWL-SET-3PC", H.TOWEL_SET, H.STORES["Towel Sets"], "Towel Pieces Store"),
		("BED-SET-KING", H.BED_SET, H.STORES["Bed Sets"], "Sheet Pieces Store"),
	)):
		wo = make_wo(item, spec["qty"], "Set Assembly", ht(13), hd(9), stores=stores)
		rows = transfer_rows(spec["transfer"], piece_store, batched=True) + transfer_rows(spec["packing"], "Packing Material Store")
		ht_transfer(wo, f"13-{i}", hd(9), f"0{8 + i}:00:00", rows)
		produce(wo, spec["qty"], ht(f"13-{i}"), hd(9), f"{17 + i}:00:00", None, "QA-01")
	log("HT-13 set assembly done")


def step_15_packing_lists():
	for i, (item, spec) in enumerate(H.CARTONS.items()):
		so = frappe.db.get_value("Sales Order", {"po_no": spec["so"], "docstatus": 1})
		if frappe.db.exists("Carton Packing List", {"sales_order": so, "item_code": item, "docstatus": 1}):
			continue
		length, width, height = spec["dims"]
		cpl = frappe.get_doc({
			"doctype": "Carton Packing List", "company": company(), "posting_date": day(hd(10)), "sales_order": so,
			"customer": frappe.db.get_value("Sales Order", so, "customer"), "item_code": item,
			"net_kg_per_unit": spec["net_kg_per_unit"], "carton_length_cm": length, "carton_width_cm": width,
			"carton_height_cm": height, "pcs_per_carton": 0,
		})
		cpl.flags.ignore_permissions = True
		cpl.insert()
		cpl.generate_cartons()
		cpl.reload()
		cpl.submit()
		log(f"HT-15 packing list {cpl.name}: {cpl.total_cartons} cartons × {cpl.pcs_per_carton}, {cpl.total_qty} sets, "
			f"{cpl.total_gross_kg} kg gross, {cpl.total_cbm} CBM, first SSCC {cpl.cartons[0].sscc}")
		if frappe.db.exists("Print Format", "Carton Label"):
			html = frappe.get_print("Carton Packing List", cpl.name, "Carton Label")
			assert html.count("<svg") >= cpl.total_cartons, "SSCC barcodes missing"
			log(f"  rendered {cpl.total_cartons} carton labels")


def step_16_deliveries():
	for i, (item, spec) in enumerate(H.CARTONS.items()):
		step = ht(f"16-{i}")
		so = frappe.db.get_value("Sales Order", {"po_no": spec["so"], "docstatus": 1})
		cpl = frappe.get_doc("Carton Packing List", {"sales_order": so, "item_code": item, "docstatus": 1})
		dn_name = cpl.create_delivery_note(day(hd(11)), f"{10 + i}:00:00")
		dn = frappe.get_doc("Delivery Note", dn_name)
		if dn.docstatus == 0:
			dn.po_no = f"{dn.po_no or ''} {tag(step)}".strip()
			dn.save()
			for row in dn.items:
				if frappe.get_cached_value("Item", row.item_code, "inspection_required_before_delivery"):
					qi = make_qi(row.item_code, "Delivery Note", dn.name, H.AQL, "Outgoing", day(hd(11)), row.batch_no,
						row.name, remarks=f"{tag(ht(14))} AQL 2.5 final inspection", sample_size=80)
					log(f"HT-14 AQL {qi.name}: {qi.status}")
			dn.reload()
			for row in dn.items:
				row.quality_inspection = frappe.db.get_value(
					"Quality Inspection", {"reference_name": dn.name, "child_row_reference": row.name, "docstatus": 1})
			dn.save()
			dn.submit()
		si = make_invoice(dn.name, step, hd(11), PLANT)
		log(f"HT-16 delivered {dn.name} from {cpl.name}, invoiced {si}")

	step = ht("16-W")
	if not frappe.db.get_value("Delivery Note", {"po_no": ["like", f"%{tag(step)}%"], "docstatus": 1}):
		items = []
		for item, store, rate in H.SECONDS_SALE["items"]:
			qty = flt(frappe.db.get_value("Bin", {"item_code": item, "warehouse": wh(store)}, "actual_qty"), 3)
			if qty > 0:
				items.append({"item_code": item, "qty": qty, "rate": rate, "warehouse": wh(store)})
		if items:
			dn = frappe.get_doc({
				"doctype": "Delivery Note", "company": company(), "customer": H.SECONDS_SALE["customer"],
				"set_posting_time": 1, "posting_date": day(hd(11)), "posting_time": "16:00:00", "po_no": tag(step),
				"selling_price_list": "Standard Selling", "items": items,
			})
			dn.flags.ignore_permissions = True
			dn.insert()
			dn.submit()
			si = make_invoice(dn.name, step, hd(11), PLANT, wh("Waste Sales"))
			log(f"HT-16 seconds and rags sold {dn.name}, invoiced {si}")


def process_reposts() -> None:
	"""HT entries are back-dated between denim ones on shared items (cotton, caustic): settle valuation now."""
	from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost_entries

	pending = frappe.db.count("Repost Item Valuation", {"status": ["in", ["Queued", "In Progress"]], "docstatus": 1})
	if pending:
		repost_entries()
		log(f"Processed {pending} back-dated valuation reposts")


STEPS = [
	step_01_opening_stock, step_02_sales_orders, step_03_spinning, step_04_terry_weaving, step_06_processing,
	step_07_flat_weaving, step_08_printing, step_09_ctp_orders, step_10_weight_checks, step_11_towel_ctp,
	step_12_sheet_ctp, step_13_set_assembly, step_15_packing_lists, step_16_deliveries,
]


def run_all(upto: int | None = None) -> None:
	"""Run every HT step in order (optionally only the first `upto`). Commits after each step."""
	frappe.flags.mute_emails = True
	log(f"Home Textile demo journey: HT-01 = {day(hd(0))} (today {today()})")
	for i, fn in enumerate(STEPS, start=1):
		if upto and i > int(upto):
			break
		fn()
		frappe.db.commit()
	process_reposts()
	frappe.db.commit()
