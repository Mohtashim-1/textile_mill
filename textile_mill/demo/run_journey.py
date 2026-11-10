"""Denim demo journey (Part B §11). Idempotent; posting dates strictly increase.

Run on a site that has run `textile_mill.setup.masters.run`:
    bench --site <site> execute textile_mill.demo.run_journey.run_all
Every created document carries a `[DEMO-STEP-NN]` tag (remarks / description / po_no) and each
step skips itself when its tagged output already exists.
"""

import frappe
from frappe.utils import add_days, cint, flt, get_datetime, getdate, today

from textile_mill.demo import data
from textile_mill.manufacturing import (
	available_batches,
	build_manufacture_entry,
	complete_operations,
	make_corrective_job_card,
	make_material_entry,
	make_transfer_entry,
	new_batch,
	pick_batches,
)
from textile_mill.utils import wh

D0_KEY = "textile_demo_d0"


# ---------------------------------------------------------------- helpers
def d0():
	value = frappe.db.get_default(D0_KEY)
	if not value:
		value = str(getdate(add_days(today(), data.D0_OFFSET_DAYS)))
		frappe.db.set_default(D0_KEY, value)
	return getdate(value)


def day(n: int):
	return getdate(add_days(d0(), n))


def tag(step: int | str) -> str:
	return f"[DEMO-STEP-{step:02d}]" if isinstance(step, int) else f"[DEMO-{step}]"


def company() -> str:
	return frappe.db.get_single_value("Global Defaults", "default_company")


def tagged(doctype: str, step, field: str = "remarks", extra: dict | None = None) -> str | None:
	filters = {field: ["like", f"%{tag(step)}%"], "docstatus": ["<", 2], **(extra or {})}
	return frappe.db.get_value(doctype, filters)


def log(msg: str) -> None:
	print(msg)


def bom_of(item: str) -> str:
	return frappe.db.get_value("BOM", {"item": item, "is_default": 1, "is_active": 1, "docstatus": 1})


def make_qi(item_code, reference_type, reference_name, readings, inspection_type, posting, batch_no=None,
		child_row=None, template=None, remarks=None, sample_size=1):
	qi = frappe.new_doc("Quality Inspection")
	qi.update(
		{
			"inspection_type": inspection_type,
			"reference_type": reference_type,
			"reference_name": reference_name,
			"item_code": item_code,
			"batch_no": batch_no,
			"child_row_reference": child_row,
			"sample_size": sample_size,
			"report_date": posting,
			"inspected_by": "Administrator",
			"remarks": remarks,
			"quality_inspection_template": template
			or frappe.db.get_value("Item", item_code, "quality_inspection_template"),
		}
	)
	qi.get_item_specification_details()
	for r in qi.readings:
		if r.specification in readings:
			r.reading_1 = str(readings[r.specification])
	qi.flags.ignore_permissions = True
	qi.insert()
	qi.submit()
	return qi


def make_wo(
	item: str,
	qty: float,
	stage: str,
	step: int | str,
	n_day: int,
	dye_recipe: str | None = None,
	stores: tuple[str, str, str] | None = None,
) -> str:
	existing = tagged("Work Order", step, "description", {"production_item": item})
	if existing:
		return existing
	source, wip, fg = stores or data.WO_WAREHOUSES[stage]
	wo = frappe.get_doc(
		{
			"doctype": "Work Order",
			"company": company(),
			"production_item": item,
			"bom_no": frappe.db.get_value("Dye Recipe", dye_recipe, "bom") if dye_recipe else bom_of(item),
			"dye_recipe": dye_recipe,
			"use_multi_level_bom": 0,
			"qty": qty,
			"source_warehouse": wh(source),
			"wip_warehouse": wh(wip),
			"fg_warehouse": wh(fg),
			"scrap_warehouse": wh("Waste Store"),
			"planned_start_date": f"{day(n_day)} 07:00:00",
			"description": f"{tag(step)} {stage} demo order",
		}
	)
	wo.flags.ignore_permissions = True
	wo.insert()
	wo.submit()
	log(f"  Work Order {wo.name}: {item} × {qty}")
	return wo.name


def transfer(wo: str, items: list[tuple[str, float]], step: int, n_day: int, time: str, note: str = "") -> None:
	trf_tag = f"{step:02d}-TRF{note}"
	if tagged("Stock Entry", trf_tag, extra={"work_order": wo}):
		return
	rows = [
		{"item_code": i, "qty": q, "s_warehouse": wh(data.ISSUE_STORE.get(i, data.CHEM_STORE))} for i, q in items
	]
	se = make_transfer_entry(
		wo, rows, day(n_day), time, remarks=f"{tag(trf_tag)} transfer", fg_qty=0 if note else None
	)
	log(f"  Transfer {se.name} → {wo}")


def produce(
	wo: str,
	qty: float,
	step: int,
	n_day: int,
	time: str,
	readings: dict | None,
	operator: str | None = None,
	batch_fields: dict | None = None,
	fail_readings: dict | None = None,
	on_fail=None,
	links: dict | None = None,
) -> str:
	"""Manufacture with job cards + QI (when the BOM requires it). Returns the Stock Entry name."""
	existing = tagged("Stock Entry", step, extra={"work_order": wo, "purpose": "Manufacture", "docstatus": 1})
	if existing:
		return existing
	posting = get_datetime(f"{day(n_day)} {time}")
	complete_operations(wo, qty, posting, operator)
	wo_doc = frappe.get_doc("Work Order", wo)
	draft = tagged("Stock Entry", step, extra={"work_order": wo, "purpose": "Manufacture", "docstatus": 0})
	if draft:
		se = frappe.get_doc("Stock Entry", draft)
	else:
		batch = new_batch(
			wo_doc.production_item,
			manufacturing_date=day(n_day),
			dm_stage=wo_doc.dm_stage,
			dm_source_doctype="Work Order",
			dm_source_doc=wo,
			**(batch_fields or {}),
		)
		se = build_manufacture_entry(wo, qty, day(n_day), time, fg_batch=batch, remarks=f"{tag(step)} manufacture", **(links or {}))
		se.insert()

	def fg_row():
		return next(r for r in se.items if r.is_finished_item)

	if se.inspection_required:
		template = frappe.db.get_value("BOM", wo_doc.bom_no, "quality_inspection_template")
		if fail_readings and not frappe.db.exists("Quality Inspection", {"reference_name": se.name, "status": "Rejected"}):
			qi = make_qi(wo_doc.production_item, "Stock Entry", se.name, fail_readings, "In Process", day(n_day),
				fg_row().batch_no, fg_row().name, template, f"{tag(step)} first inspection")
			log(f"  QI {qi.name}: {qi.status}")
		if fail_readings and on_fail:
			batch = fg_row().batch_no
			on_fail(se)
			se.reload()
			se.get_items()
			for r in se.items:
				if r.is_finished_item:
					r.batch_no = batch
					r.use_serial_batch_fields = 1
			se.save()
		qi = make_qi(wo_doc.production_item, "Stock Entry", se.name, readings or {}, "In Process", day(n_day),
			fg_row().batch_no, fg_row().name, template, f"{tag(step)} final inspection")
		log(f"  QI {qi.name}: {qi.status}")
		se.reload()
		fg_row().quality_inspection = qi.name
		se.save()
	se.submit()
	log(f"  Manufacture {se.name}: {qty} {wo_doc.production_item}")
	return se.name


def wo_by_step(step: int, item: str) -> str:
	return tagged("Work Order", step, "description", {"production_item": item})


# ---------------------------------------------------------------- steps
def step_01_opening_stock():
	if tagged("Stock Entry", 1):
		return
	rows = []
	for store, items in data.OPENING_STOCK.items():
		for item, qty in items:
			batch = None
			if frappe.get_cached_value("Item", item, "has_batch_no"):
				batch = new_batch(item, manufacturing_date=day(0), dm_stage="Raw")
			rows.append({"item_code": item, "qty": qty, "t_warehouse": wh(store), "batch_no": batch,
				"basic_rate": frappe.db.get_value("Item", item, "valuation_rate")})
	se = make_material_entry("Material Receipt", company(), rows, day(0), "08:00:00", remarks=f"{tag(1)} opening stock")
	log(f"Step 01 opening stock {se.name}")


def make_so(spec: dict, step: int | str, n_day: int = 0) -> str:
	existing = frappe.db.get_value("Sales Order", {"po_no": spec["po_no"], "docstatus": 1})
	if existing:
		return existing
	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"company": company(),
			"customer": spec["customer"],
			"po_no": spec["po_no"],
			"transaction_date": day(n_day),
			"delivery_date": day(spec["delivery_day"]),
			"selling_price_list": "Standard Selling",
			"items": [
				{"item_code": i, "qty": q, "rate": r, "delivery_date": day(spec["delivery_day"])} for i, q, r in spec["items"]
			],
		}
	)
	so.flags.ignore_permissions = True
	so.insert()
	so.submit()
	return so.name


def step_02_sales_orders():
	so_fab, so_jns = make_so(data.SO_FAB, 2), make_so(data.SO_JNS, 2)
	log(f"Step 02 sales orders {so_fab}, {so_jns}")


def step_03_production_plan():
	so_names = [frappe.db.get_value("Sales Order", {"po_no": s["po_no"], "docstatus": 1}) for s in (data.SO_FAB, data.SO_JNS)]
	if frappe.db.get_value("Production Plan Sales Order", {"sales_order": so_names[0]}, "parent"):
		return
	pp = frappe.new_doc("Production Plan")
	pp.update({"company": company(), "posting_date": day(0), "get_items_from": "Sales Order"})
	for so in so_names:
		so_doc = frappe.get_doc("Sales Order", so)
		pp.append("sales_orders", {"sales_order": so, "sales_order_date": so_doc.transaction_date,
			"customer": so_doc.customer, "grand_total": so_doc.grand_total})
	pp.get_items()
	pp.sub_assembly_warehouse = wh("Work In Progress")
	try:
		pp.get_sub_assembly_items()
	except Exception:
		frappe.log_error(title="Textile demo: production plan sub-assemblies")
	pp.flags.ignore_permissions = True
	pp.insert()
	pp.submit()
	log(f"Step 03 production plan {pp.name} ({len(pp.po_items)} FG rows, {len(pp.sub_assembly_items)} sub-assemblies)")


def step_04_purchases():
	for idx, spec in enumerate(data.PURCHASES):
		step = f"04-{idx + 1}"
		if tagged("Purchase Receipt", step):
			continue
		batch = new_batch(spec["item"], manufacturing_date=day(1), dm_stage="Raw")
		pr = frappe.get_doc(
			{
				"doctype": "Purchase Receipt",
				"company": company(),
				"supplier": spec["supplier"],
				"set_posting_time": 1,
				"posting_date": day(1),
				"posting_time": f"0{8 + idx}:00:00",
				"buying_price_list": "Standard Buying",
				"remarks": f"{tag(step)} purchase",
				"items": [
					{
						"item_code": spec["item"],
						"qty": spec["qty"],
						"rate": spec["rate"],
						"warehouse": wh(spec["warehouse"]),
						"batch_no": batch,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		pr.flags.ignore_permissions = True
		pr.insert()
		qi = make_qi(spec["item"], "Purchase Receipt", pr.name, spec["qi"], "Incoming", day(1), batch,
			pr.items[0].name, remarks=f"{tag(step)} incoming", sample_size=10)
		pr.reload()
		pr.items[0].quality_inspection = qi.name
		pr.save()
		pr.submit()
		log(f"Step 04 purchase {pr.name}: {spec['qty']} {spec['item']} (QI {qi.status})")


def step_05_recycling():
	s = data.RECYCLING
	wo = make_wo("RF-PRE-A", s["qty"], "Cotton Recycling", 5, 2)
	transfer(wo, s["transfer"], 5, 2, "08:00:00")
	produce(wo, s["qty"], 5, 2, "18:00:00", s["qi"], s["operator"])
	log("Step 05 recycling done")


def step_06_fiber_dyeing():
	s = data.FIBER_DYEING
	wo = make_wo("DF-BLK", s["qty"], "Fiber Dyeing", 6, 3, dye_recipe=s["recipe"])
	transfer(wo, s["transfer"], 6, 3, "08:00:00")
	produce(wo, s["qty"], 6, 3, "18:00:00", s["qi"], s["operator"])
	log("Step 06 fiber dyeing done")


def step_07_spinning_warp():
	s = data.SPIN_WARP
	wo = make_wo("YRN-W-10NE-60R", s["qty"], "Spinning", 7, 4)
	transfer(wo, s["transfer"], 7, 4, "08:00:00")
	produce(wo, s["qty"], 7, 4, "20:00:00", s["qi"], s["operator"], {"dm_beam_nos": ""})
	log("Step 07 spinning warp done")


def step_08_spinning_weft():
	s = data.SPIN_WEFT
	wo = make_wo("YRN-F-16NE-BLK", s["qty"], "Spinning", 8, 5)
	transfer(wo, s["transfer"], 8, 5, "08:00:00")
	produce(wo, s["qty"], 8, 5, "20:00:00", s["qi"], s["operator"])
	log("Step 08 spinning weft done")


def step_09_indigo_dyeing():
	s = data.INDIGO
	wo = make_wo("IWY-10NE-IND", s["qty"], "Indigo Dyeing", 9, 6, dye_recipe=s["recipe"])
	transfer(wo, s["transfer"], 9, 6, "06:30:00")
	for log_spec in s["range_logs"]:
		log_tag = "09-" + log_spec["shift"]
		if tagged("Indigo Range Log", log_tag):
			continue
		irl = frappe.get_doc(
			{
				"doctype": "Indigo Range Log",
				"posting_date": day(6),
				"shift": log_spec["shift"],
				"work_order": wo,
				"workstation": "IRR-01",
				"operator": s["operator"],
				"range_speed_m_min": log_spec["speed"],
				"no_of_dips": log_spec["dips"],
				"set_of_ends": log_spec["ends"],
				"beams": s["beams"],
				"remarks": f"{tag(log_tag)} range log",
				"readings": [
					{"reading_time": t, "ph": ph, "indigo_g_l": ind, "hydro_g_l": hyd, "redox_mv": rdx, "temperature_c": tmp}
					for t, ph, ind, hyd, rdx, tmp in log_spec["readings"]
				],
			}
		)
		irl.flags.ignore_permissions = True
		irl.insert()
		irl.submit()
		log(f"Step 09 range log {irl.name}: {irl.status} ({irl.out_of_spec_count} out of spec)")


def step_10_indigo_corrective_and_manufacture():
	s = data.INDIGO
	wo = wo_by_step(9, "IWY-10NE-IND")

	def on_fail(se):
		if not frappe.db.exists("Job Card", {"work_order": wo, "is_corrective_job_card": 1, "docstatus": 1}):
			jc = make_corrective_job_card(
				wo, "Rope Indigo Dyeing", s["corrective"]["operation"], s["corrective"]["minutes"],
				f"{day(6)} 22:00:00", s["corrective"]["remarks"], s["operator"],
			)
			log(f"  Corrective job card {jc}")
		transfer(wo, s["extra_chemicals"], 10, 6, "23:40:00", note="-REDYE")

	produce(
		wo, s["qty"], 10, 6, "23:50:00", s["qi_pass"], s["operator"],
		batch_fields={"dm_beam_nos": s["beams"]}, fail_readings=s["qi_fail"], on_fail=on_fail,
	)
	log("Step 10 indigo corrective + manufacture done")


def step_11_weaving_transfer():
	s = data.WEAVING
	wo = make_wo("GF-DM1150", s["qty"], "Weaving", 11, 7)
	transfer(wo, s["transfer"], 11, 7, "06:00:00")
	log("Step 11 weaving transfer done")


def step_12_loom_shifts():
	wo = wo_by_step(11, "GF-DM1150")
	for i, (shift, rows) in enumerate(zip(data.WEAVING["shifts"], data.loom_rows())):
		if frappe.db.exists("Loom Shift Production", {"work_order": wo, "shift": shift, "docstatus": 1}):
			continue
		times = {"A": "15:00:00", "B": "23:00:00", "C": "23:30:00"}
		lsp = frappe.get_doc(
			{
				"doctype": "Loom Shift Production",
				"posting_date": day(7 + i),
				"posting_time": times[shift],
				"shift": shift,
				"work_order": wo,
				"supervisor": "WEAVER-01",
				"loom_type": "Air-jet Denim",
				"looms": rows,
			}
		)
		lsp.flags.ignore_permissions = True
		lsp.insert()
		lsp.submit()
		log(f"Step 12 loom shift {lsp.name}: {lsp.total_meters} m @ {lsp.avg_efficiency_pct}% → {lsp.grey_batch}")


def step_13_close_weaving():
	wo = frappe.get_doc("Work Order", wo_by_step(11, "GF-DM1150"))
	log(f"Step 13 weaving produced {wo.produced_qty} m, status {wo.status}")


def step_14_finishing():
	s = data.FINISHING
	wo = make_wo("FF-DM1150", s["qty"], "Finishing", 14, 10)
	if not tagged("Stock Entry", "14-TRF", extra={"work_order": wo}):
		grey = pick_batches("GF-DM1150", wh("Grey Fabric Store"), 10500)
		rows = [{"item_code": "GF-DM1150", "qty": q, "s_warehouse": wh("Grey Fabric Store"), "batch_no": b} for b, q in grey]
		rows.append({"item_code": "CHM-FIN", "qty": s["fin_kg"], "s_warehouse": wh(data.CHEM_STORE)})
		make_transfer_entry(wo, rows, day(10), "07:00:00", remarks=f"{tag('14-TRF')} transfer")
	produce(wo, s["qty"], 14, 10, "20:00:00", s["qi"], "QA-01", {"dm_width_inch": 64, "dm_gsm": 391})
	log("Step 14 finishing done")


def step_15_roll_inspection():
	lot = frappe.db.get_value("Batch", {"item": "FF-DM1150", "dm_source_doctype": "Work Order"}, "name", order_by="creation desc")
	if frappe.db.exists("Fabric Roll Inspection", {"lot_batch": lot, "docstatus": 1}):
		return
	rolls, defects = data.fabric_rolls()
	fri = frappe.get_doc(
		{
			"doctype": "Fabric Roll Inspection",
			"company": company(),
			"inspection_date": day(11),
			"inspector": "QA-01",
			"lot_item": "FF-DM1150",
			"lot_batch": lot,
			"source_warehouse": wh("Finished Lot Store"),
			"fabric_width_inch": 64,
			"rolls": rolls,
			"defects": defects,
		}
	)
	fri.flags.ignore_permissions = True
	fri.insert()
	fri.submit()
	log(f"Step 15 roll inspection {fri.name}: A {fri.a_pct}% B {fri.b_pct}% R {fri.rejected_pct}% → {fri.stock_entry}")


def step_16_print_roll_tags():
	if not frappe.db.exists("Print Format", "Fabric Roll Tag"):
		log("Step 16 skipped (print format not installed)")
		return
	batches = frappe.get_all("Batch", filters={"item": "FF-DM1150-A"}, pluck="name", order_by="creation asc", limit=3)
	for b in batches:
		html = frappe.get_print("Batch", b, "Fabric Roll Tag")
		assert "svg" in html.lower(), "QR missing"
	log(f"Step 16 rendered {len(batches)} roll tags")


def step_17_cut_plan():
	so = frappe.db.get_value("Sales Order", {"po_no": data.SO_JNS["po_no"], "docstatus": 1})
	if frappe.db.exists("Cut Plan", {"sales_order": so, "docstatus": 1}):
		return
	c = data.CUT_PLAN
	cp = frappe.get_doc(
		{
			"doctype": "Cut Plan",
			"company": company(),
			"posting_date": day(12),
			"sales_order": so,
			"style_template": "JNS-SLIM-UW",
			"fabric_item": "FF-DM1150-A",
			"marker_length_m": c["marker_length_m"],
			"plies": c["plies"],
			"end_bit_allowance_pct": c["end_bit_allowance_pct"],
			"size_ratio": [{"size": s, "ratio": r} for s, r in c["ratio"]],
		}
	)
	cp.flags.ignore_permissions = True
	cp.insert()
	cp.allocate_rolls()
	cp.reload()
	cp.submit()
	bundles = frappe.db.count("Bundle Ticket", {"cut_plan": cp.name})
	log(f"Step 17 cut plan {cp.name}: {cp.total_pieces} pcs, issued {cp.fabric_issued_m} m, "
		f"variance {cp.cutting_variance_m} m ({cp.cutting_variance_pct}%), {bundles} bundles")


def step_18_stitching():
	from textile_mill.textile_mill.doctype.bundle_ticket.bundle_ticket import complete_work_order, set_status

	so = frappe.db.get_value("Sales Order", {"po_no": data.SO_JNS["po_no"], "docstatus": 1})
	cp = frappe.db.get_value("Cut Plan", {"sales_order": so, "docstatus": 1})
	bundles = frappe.get_all("Bundle Ticket", filters={"cut_plan": cp}, fields=["name", "status"], order_by="name asc")
	for i, b in enumerate(bundles):
		if b.status in ("Cut", "In Stitching"):
			line = data.STITCH_LINES[i % len(data.STITCH_LINES)]
			set_status(b.name, "In Stitching", line)
			set_status(b.name, "Stitched", line, f"{day(13 if i < len(bundles) / 2 else 14)} 16:00:00")
	for k, wo in enumerate(frappe.get_all("Work Order", filters={"cut_plan": cp, "docstatus": 1}, pluck="name", order_by="name asc")):
		if frappe.db.get_value("Work Order", wo, "status") != "Completed":
			complete_work_order(wo, str(day(14)), f"1{7 + k}:00:00")
	log(f"Step 18 stitched {len(bundles)} bundles, work orders completed")


def step_19_subcontract_wash():
	from erpnext.buying.doctype.purchase_order.purchase_order import make_subcontracting_order
	from erpnext.controllers.subcontracting_controller import make_rm_stock_entry
	from erpnext.subcontracting.doctype.subcontracting_order.subcontracting_order import make_subcontracting_receipt

	w = data.WASH
	po_name = frappe.db.get_value("Purchase Order", {"order_confirmation_no": tag(19), "docstatus": 1})
	if not po_name:
		po = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"company": company(),
				"supplier": w["supplier"],
				"is_subcontracted": 1,
				"transaction_date": day(15),
				"schedule_date": day(18),
				"supplier_warehouse": wh("Clean Wash Co."),
				"set_warehouse": wh("Garment FG Store"),
				"order_confirmation_no": tag(19),
				"items": [
					{"item_code": w["service"], "qty": q, "rate": w["rate"], "fg_item": f"JNS-SLIM-SW-{size}",
						"fg_item_qty": q, "schedule_date": day(18), "warehouse": wh("Garment FG Store")}
					for size, q in w["qty"].items()
				],
			}
		)
		po.flags.ignore_permissions = True
		po.insert()
		po.submit()
		po_name = po.name
	sco_name = frappe.db.get_value("Subcontracting Order", {"purchase_order": po_name, "docstatus": 1})
	if not sco_name:
		sco = make_subcontracting_order(po_name)
		sco.transaction_date = day(15)
		sco.supplier_warehouse = wh("Clean Wash Co.")
		sco.set_warehouse = wh("Garment FG Store")
		for row in sco.items:
			row.warehouse = wh("Garment FG Store")
		sco.flags.ignore_permissions = True
		sco.insert()
		sco.submit()
		sco_name = sco.name
	if not frappe.db.exists("Stock Entry", {"subcontracting_order": sco_name, "purpose": "Send to Subcontractor", "docstatus": 1}):
		se = frappe.get_doc(make_rm_stock_entry(sco_name, order_doctype="Subcontracting Order"))
		se.set_posting_time = 1
		se.posting_date = day(15)
		se.posting_time = "10:00:00"
		se.remarks = f"{tag(19)} send to subcontractor"
		for row in se.items:
			row.s_warehouse = wh("Unwashed Garment Store") if row.item_code.startswith("JNS-") else wh("Trims Store")
			row.t_warehouse = wh("Clean Wash Co.")
		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		log(f"  Sent to subcontractor {se.name}")
	if not frappe.db.exists("Subcontracting Receipt", {"remarks": ["like", f"%{tag(19)}%"], "docstatus": 1}):
		scr = make_subcontracting_receipt(sco_name)
		scr.set_posting_time = 1
		scr.posting_date = day(18)
		scr.posting_time = "15:00:00"
		scr.remarks = f"{tag(19)} washed jeans received"
		scr.flags.ignore_permissions = True
		scr.insert()
		scr.submit()
		log(f"  Subcontracting receipt {scr.name}")
	log(f"Step 19 subcontract wash done ({po_name}, {sco_name})")


def make_delivery(so: str, step: int, n_day: int, time: str, rows: list[dict] | None = None, qi_readings=None) -> str:
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

	existing = frappe.db.get_value("Delivery Note", {"po_no": ["like", f"%{tag(step)}%"], "docstatus": 1})
	if existing:
		return existing
	dn = make_delivery_note(so)
	dn.set_posting_time = 1
	dn.posting_date = day(n_day)
	dn.posting_time = time
	dn.po_no = f"{dn.po_no or ''} {tag(step)}".strip()
	if rows is not None:
		so_detail = {r.item_code: r for r in dn.items}
		dn.set("items", [])
		for r in rows:
			base = so_detail[r["item_code"]].as_dict()
			for k in ("name", "idx", "parent", "parentfield", "parenttype", "doctype"):
				base.pop(k, None)
			base.update(r)
			base["use_serial_batch_fields"] = 1 if r.get("batch_no") else 0
			dn.append("items", base)
	dn.flags.ignore_permissions = True
	dn.insert()
	if qi_readings:
		for row in dn.items:
			if frappe.db.get_value("Item", row.item_code, "inspection_required_before_delivery"):
				qi = make_qi(row.item_code, "Delivery Note", dn.name, qi_readings, "Outgoing", day(n_day),
					row.batch_no, row.name, remarks=f"{tag(step)} AQL", sample_size=125)
				row.quality_inspection = qi.name
		dn.reload()
		for row in dn.items:
			row.quality_inspection = frappe.db.get_value(
				"Quality Inspection", {"reference_name": dn.name, "child_row_reference": row.name, "docstatus": 1}
			)
		dn.save()
	dn.submit()
	return dn.name


def make_invoice(dn: str, step: int, n_day: int, plant: str, income_account: str | None = None) -> str:
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

	existing = frappe.db.get_value("Sales Invoice", {"remarks": ["like", f"%{tag(step)}%"], "docstatus": 1})
	if existing:
		return existing
	si = make_sales_invoice(dn)
	si.set_posting_time = 1
	si.posting_date = day(n_day)
	si.due_date = add_days(day(n_day), 30)
	si.plant = plant
	si.remarks = f"{tag(step)} invoice"
	for row in si.items:
		row.plant = plant
		if income_account:
			row.income_account = income_account
	si.flags.ignore_permissions = True
	si.insert()
	si.submit()
	return si.name


def step_20_deliver_jeans():
	so = frappe.db.get_value("Sales Order", {"po_no": data.SO_JNS["po_no"], "docstatus": 1})
	rows = [{"item_code": f"JNS-SLIM-SW-{s}", "qty": q, "warehouse": wh("Garment FG Store")} for s, q in data.WASH["qty"].items()]
	dn = make_delivery(so, 20, 19, "11:00:00", rows, data.GARMENT_QI)
	si = make_invoice(dn, 20, 19, "Plant-3 Garments")
	log(f"Step 20 jeans delivered {dn}, invoiced {si}")


def step_21_deliver_fabric():
	so = frappe.db.get_value("Sales Order", {"po_no": data.SO_FAB["po_no"], "docstatus": 1})
	ordered = data.SO_FAB["items"][0][1]
	rows = None
	if not frappe.db.get_value("Delivery Note", {"po_no": ["like", f"%{tag(21)}%"], "docstatus": 1}):
		available = sum(q for _, q in available_batches("FF-DM1150-A", wh("Fabric A Store")))
		qty = min(ordered, flt(available, 3))
		if qty < ordered:
			log(f"  WARNING: only {qty} m A-grade available; capping SO-FAB delivery (ordered {ordered} m)")
		rows = [{"item_code": "FF-DM1150-A", "qty": q, "warehouse": wh("Fabric A Store"), "batch_no": b}
			for b, q in pick_batches("FF-DM1150-A", wh("Fabric A Store"), qty)]
	dn = make_delivery(so, 21, 20, "10:00:00", rows)
	si = make_invoice(dn, 21, 20, "Plant-2 Denim")
	delivered = frappe.db.get_value("Delivery Note", dn, "total_qty")
	log(f"Step 21 fabric delivered {dn} ({delivered} m), invoiced {si}")


def step_22_waste_sale():
	w = data.WASTE_SALE
	if not frappe.db.exists("Customer", w["customer"]):
		frappe.get_doc({"doctype": "Customer", "customer_name": w["customer"], "customer_type": "Individual",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}),
			"territory": frappe.db.get_value("Territory", {"is_group": 0})}).insert(ignore_permissions=True)
	dn_name = frappe.db.get_value("Delivery Note", {"po_no": ["like", f"%{tag(22)}%"], "docstatus": 1})
	if not dn_name:
		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": company(),
				"customer": w["customer"],
				"set_posting_time": 1,
				"posting_date": day(20),
				"posting_time": "15:00:00",
				"po_no": tag(22),
				"selling_price_list": "Standard Selling",
				"items": [{"item_code": i, "qty": q, "rate": r, "warehouse": wh("Waste Store")} for i, q, r in w["items"]],
			}
		)
		dn.flags.ignore_permissions = True
		dn.insert()
		dn.submit()
		dn_name = dn.name
	si = make_invoice(dn_name, 22, 20, "Plant-1 Spinning & Recycling", wh("Waste Sales"))
	log(f"Step 22 waste sold {dn_name}, invoiced {si}")


def step_23_utility_log():
	if tagged("Utility Consumption Log", 23):
		return
	from textile_mill.reports_lib import absorbed_utilities

	absorbed = absorbed_utilities(company(), day(0), day(21))
	lines = []
	for stage, amount in absorbed.items():
		actual = flt(amount * data.UTILITY_ACTUAL_FACTOR.get(stage, 1.05), 2)
		kwh = flt(actual / data.ELECTRICITY_RATE, 2)
		lines.append({"stage": stage, "utility_type": "Electricity kWh", "qty": kwh, "rate": data.ELECTRICITY_RATE})
	ucl = frappe.get_doc(
		{
			"doctype": "Utility Consumption Log",
			"company": company(),
			"period_from": day(0),
			"period_to": day(21),
			"remarks": f"{tag(23)} demo period actuals",
			"lines": lines,
		}
	)
	ucl.flags.ignore_permissions = True
	ucl.insert()
	ucl.submit()
	log(f"Step 23 utility log {ucl.name}: {ucl.total_amount}")


def step_24_summary():
	from textile_mill.demo.summary import print_summary

	print_summary(company(), day(0), day(21))


STEPS = [
	step_01_opening_stock, step_02_sales_orders, step_03_production_plan, step_04_purchases, step_05_recycling,
	step_06_fiber_dyeing, step_07_spinning_warp, step_08_spinning_weft, step_09_indigo_dyeing,
	step_10_indigo_corrective_and_manufacture, step_11_weaving_transfer, step_12_loom_shifts, step_13_close_weaving,
	step_14_finishing, step_15_roll_inspection, step_16_print_roll_tags, step_17_cut_plan, step_18_stitching,
	step_19_subcontract_wash, step_20_deliver_jeans, step_21_deliver_fabric, step_22_waste_sale, step_23_utility_log,
	step_24_summary,
]


def run_all(upto: int | None = None) -> None:
	"""Run every step in order (optionally stop after step `upto`). Commits after each step."""
	frappe.flags.mute_emails = True
	log(f"Textile demo journey: D0 = {d0()}")
	for i, fn in enumerate(STEPS, start=1):
		if upto and i > cint(upto):
			break
		fn()
		frappe.db.commit()
	if not upto:
		from textile_mill.demo.run_journey_ht import run_all as run_home_textile
		from textile_mill.demo.run_journey_knit import run_all as run_knitting
		from textile_mill.demo.seed_history import run as seed_history

		run_home_textile()
		run_knitting()
		seed_history()
