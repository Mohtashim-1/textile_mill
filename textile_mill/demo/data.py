"""Denim demo constants (Part B §11). All quantities, rates and day offsets live here."""

import random

from textile_mill.constants import DENIM_STAGES, STAGE_WAREHOUSES

D0_OFFSET_DAYS = -25  # D0 = today − 25 days

OPENING_STOCK = {
	"Chemicals & Dyes Store": [
		("CHM-IND", 120), ("CHM-HYD", 150), ("CHM-CAU", 120), ("CHM-WET", 20), ("CHM-SIZE", 400),
		("CHM-SBLK", 80), ("CHM-NAS", 60), ("CHM-SODA", 40), ("CHM-FIN", 120),
	],
	"Trims Store": [
		("TRM-ZIP", 2100), ("TRM-BTN", 2100), ("TRM-RVT", 12600), ("TRM-LBL", 4200), ("TRM-THR", 100),
		("TRM-POCK", 600), ("PKG-POLY", 2100),
	],
}

SO_FAB = {"customer": "Lahore Fashion Fabrics", "po_no": "DEMO-SO-FAB", "delivery_day": 20,
	"items": [("FF-DM1150-A", 6500, 1100)]}
SO_JNS = {"customer": "Urban Threads LLC", "po_no": "DEMO-SO-JNS", "delivery_day": 24,
	"items": [("JNS-SLIM-SW-30", 333, 3200), ("JNS-SLIM-SW-32", 667, 3200), ("JNS-SLIM-SW-34", 667, 3200),
		("JNS-SLIM-SW-36", 333, 3200)]}

PURCHASES = [
	{"supplier": "Karachi Textile Waste Traders", "item": "CW-PRE", "qty": 8000, "rate": 180, "warehouse": "Cotton Waste Store",
		"qi": {"Trash %": 6.2, "Moisture %": 7.8, "Avg Fiber Length (mm)": 18}},
	{"supplier": "Sindh Cotton Ginners", "item": "VC-RAW", "qty": 3000, "rate": 520, "warehouse": "Virgin Cotton Store",
		"qi": {"Trash %": 2.5, "Moisture %": 7.0, "Avg Fiber Length (mm)": 28}},
]

# stage -> (source, wip, fg) warehouses (Part B §11.2); scrap always to Waste Store.
WO_WAREHOUSES = {stage: stores for stage, stores in STAGE_WAREHOUSES.items() if stage in DENIM_STAGES and stage != "Garments"}

# Item -> store it is issued from (mixed-source transfers set s_warehouse per row).
ISSUE_STORE = {
	"CW-PRE": "Cotton Waste Store", "VC-RAW": "Virgin Cotton Store", "RF-PRE-A": "Recycled Fiber Store",
	"DF-BLK": "Dyed Fiber Store", "YRN-W-10NE-60R": "Yarn Store", "YRN-F-16NE-BLK": "Yarn Store",
	"IWY-10NE-IND": "Beam Store", "GF-DM1150": "Grey Fabric Store",
}
CHEM_STORE = "Chemicals & Dyes Store"

RECYCLING = {"qty": 6800, "transfer": [("CW-PRE", 8000)], "operator": "OP-RC-01",
	"qi": {"Avg Fiber Length (mm)": 19, "Neps per gram": 320, "Trash %": 2.1}}
FIBER_DYEING = {"qty": 970, "recipe": "DR-BLK-001", "operator": "OP-FD-01",
	"transfer": [("RF-PRE-A", 1000), ("CHM-SBLK", 62), ("CHM-NAS", 40), ("CHM-SODA", 20), ("CHM-WET", 2)],
	"qi": {"Delta E (vs standard)": 0.6, "Wash Fastness (grade)": 4}}
SPIN_WARP = {"qty": 3660, "operator": "OP-SP-01", "transfer": [("RF-PRE-A", 2496), ("VC-RAW", 1662)],
	"qi": {"Actual Count (Ne)": 10.05, "Count CV %": 1.9, "CSP": 1850}}
SPIN_WEFT = {"qty": 3000, "operator": "OP-SP-01", "transfer": [("DF-BLK", 960), ("RF-PRE-A", 1500), ("VC-RAW", 948)],
	"qi": {"Actual Count (Ne)": 16.1, "Count CV %": 2.1, "IPI (per km)": 240}}
INDIGO = {
	"qty": 3620, "recipe": "DR-IND-001", "operator": "OP-IND-01",
	"transfer": [("YRN-W-10NE-60R", 3660), ("CHM-IND", 77.8), ("CHM-HYD", 91.5), ("CHM-CAU", 73.2), ("CHM-WET", 7.3),
		("CHM-SIZE", 292.8)],
	"qi_fail": {"Delta E (vs standard)": 1.8, "Rubbing Fastness Dry (grade)": 3.5, "Size Pick-up %": 12.1},
	"corrective": {"operation": "Shade Correction Re-dip", "minutes": 90, "remarks": "Shade top-up re-dip"},
	"extra_chemicals": [("CHM-IND", 2.5), ("CHM-HYD", 3.0)],
	"qi_pass": {"Delta E (vs standard)": 0.7, "Rubbing Fastness Dry (grade)": 3.5, "Size Pick-up %": 12.4},
	"beams": "BM-01, BM-02, BM-03, BM-04, BM-05, BM-06, BM-07, BM-08, BM-09",
	"range_logs": [
		{"shift": "A", "speed": 32, "dips": 8, "ends": 4000, "readings": [
			("07:30:00", 11.4, 2.3, 2.1, -790, 28), ("09:30:00", 11.5, 2.4, 2.0, -795, 28),
			("11:30:00", 11.3, 2.2, 2.2, -785, 29), ("13:30:00", 11.6, 2.4, 2.1, -800, 29)]},
		{"shift": "B", "speed": 32, "dips": 8, "ends": 4000, "readings": [
			("15:30:00", 11.5, 2.3, 2.0, -790, 28), ("17:30:00", 12.1, 2.5, 1.8, -770, 30),
			("19:30:00", 12.1, 2.6, 1.7, -765, 30), ("21:30:00", 11.6, 2.4, 2.1, -795, 29)]},
	],
}
WEAVING = {"qty": 10500, "transfer": [("IWY-10NE-IND", 3570), ("YRN-F-16NE-BLK", 2940)], "shifts": ["A", "B", "C"],
	"meters_per_shift": 3500, "looms": [f"LM-{i:03d}" for i in range(1, 25)],
	"weavers": [f"WEAVER-{i:02d}" for i in range(1, 9)]}
FINISHING = {"qty": 10000, "fin_kg": 100,
	"qi": {"GSM": 391, "Width (inch)": 64.1, "Shrinkage Warp %": 1.8, "Shrinkage Weft %": 2.2, "Skew %": 2.5}}

CUT_PLAN = {"marker_length_m": 8.25, "plies": 334, "end_bit_allowance_pct": 2,
	"ratio": [("30", 1), ("32", 2), ("34", 2), ("36", 1)]}
STITCH_LINES = ["SL-01", "SL-02", "SL-03", "SL-04"]
WASH = {"supplier": "Clean Wash Co.", "service": "SRV-WASH", "rate": 120,
	"qty": {"30": 333, "32": 667, "34": 667, "36": 333}}
GARMENT_QI = {"Major Defects Found": 3, "Waist Measurement Deviation (cm)": 0.6}
WASTE_SALE = {"customer": "Local Waste Buyer", "items": [("WST-HARD", 600, 40), ("WST-SOFT", 666, 90), ("WST-FAB", 84, 30)]}

# Actual utilities ≈ absorbed × factor (Part B step 23: ±5–12%).
UTILITY_ACTUAL_FACTOR = {
	"Cotton Recycling": 1.08, "Fiber Dyeing": 1.12, "Spinning": 1.06, "Indigo Dyeing": 1.10,
	"Weaving": 0.95, "Finishing": 1.07, "Garments": 1.05,
}
ELECTRICITY_RATE = 60  # PKR / kWh


def loom_rows(seed: int = 42) -> list[list[dict]]:
	"""3 shifts × 24 looms; efficiency 78–92 %, metres scaled so each shift totals exactly 3,500 m."""
	rng = random.Random(seed)
	shifts = []
	for _shift in WEAVING["shifts"]:
		rows = []
		for i, loom in enumerate(WEAVING["looms"]):
			eff = round(rng.uniform(78, 92), 1)
			rpm = rng.choice([700, 720, 750, 780])
			raw = rpm * 60 * 8 * eff / 100 / (44 * 39.37)
			rows.append({"loom": loom, "weaver": WEAVING["weavers"][i // 3], "rpm": rpm, "picks_per_inch": 44,
				"efficiency_pct": eff, "raw": raw, "warp_breaks": rng.randint(2, 9), "weft_breaks": rng.randint(4, 14),
				"stop_minutes": rng.randint(10, 60)})
		total = sum(r["raw"] for r in rows)
		meters = [round(r["raw"] * WEAVING["meters_per_shift"] / total, 2) for r in rows]
		meters[-1] = round(WEAVING["meters_per_shift"] - sum(meters[:-1]), 2)
		for r, m in zip(rows, meters):
			r["meters"] = m
			r.pop("raw")
		shifts.append(rows)
	return shifts


def fabric_rolls(seed: int = 42) -> tuple[list[dict], list[dict]]:
	"""100 rolls summing exactly 10,000 m with defects giving 94 A / 5 B / 1 Rejected."""
	rng = random.Random(seed)
	raw = [rng.uniform(95, 105) for _ in range(100)]
	scale = 10000 / sum(raw)
	lengths = [round(x * scale, 1) for x in raw]
	lengths[-1] = round(10000 - sum(lengths[:-1]), 1)
	b_rolls = {17, 38, 55, 71, 88}
	r_rolls = {63}
	codes = ["SLB", "MPK", "BEN", "STN", "SHD", "CRS"]
	rolls, defects = [], []
	for i, length in enumerate(lengths):
		roll_no = f"R-{i + 1:03d}"
		gsm = round(rng.uniform(388, 394), 1)
		rolls.append({"roll_no": roll_no, "length_m": length, "width_inch": 64, "gsm": gsm,
			"roll_weight_kg": round(length * 64 * 0.0254 * gsm / 1000, 2),
			"shade_group": rng.choice(["S1", "S1", "S2"])})
		# Points target per roll: A ≈ 22–36, B ≈ 60–72, Rejected ≈ 95.
		target = 95 if i in r_rolls else rng.randint(60, 72) if i in b_rolls else rng.randint(22, 36)
		if i in r_rolls:
			defects.append({"roll_no": roll_no, "defect_type": "HOL", "defect_length_inch": 1, "position_m": 12.0})
			target -= 4
		while target > 0:
			pts = min(target, rng.choice([1, 2, 3, 4]))
			inch = {1: 2, 2: 5, 3: 8, 4: 11}[pts]
			defects.append({"roll_no": roll_no, "defect_type": rng.choice(codes), "defect_length_inch": inch,
				"position_m": round(rng.uniform(1, length - 1), 1)})
			target -= pts
	return rolls, defects
