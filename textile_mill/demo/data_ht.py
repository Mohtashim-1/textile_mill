"""Home Textile demo constants (Part D §D7). Day numbers are offsets from the HT start (denim D0 + HT_OFFSET)."""

import random

HT_OFFSET = 2  # HT-01 posts on denim day 2 so the whole story fits before today

STORES = {
	"Spinning": ("Virgin Cotton Store", "Spinning WIP", "HT Yarn Store"),
	"Terry Weaving": ("HT Yarn Store", "Terry Weaving WIP", "Grey Terry Store"),
	"Flat Weaving": ("HT Yarn Store", "Flat Weaving WIP", "Grey Sheeting Store"),
	"Processing": ("Grey Terry Store", "Processing WIP", "Processed Terry Store"),
	"Printing": ("Grey Sheeting Store", "Printing WIP", "Processed Sheeting Store"),
	"Towel CTP": ("Processed Terry Store", "CTP WIP", "Towel Pieces Store"),
	"Sheet CTP": ("Processed Sheeting Store", "CTP WIP", "Sheet Pieces Store"),
	"Towel Sets": ("Towel Pieces Store", "Set Assembly WIP", "HT FG Store"),
	"Bed Sets": ("Sheet Pieces Store", "Set Assembly WIP", "HT FG Store"),
}

OPENING_STOCK = {
	"Chemicals & Dyes Store": [
		("CHM-H2O2", 150), ("CHM-OBA", 15), ("CHM-SOFT", 120), ("CHM-PIG", 200), ("CHM-CAU", 100), ("CHM-WET", 20),
	],
	"Trims Store": [("TRM-HEM-THR", 60), ("TRM-CARE-LBL", 13000), ("TRM-LOOP", 600)],
	"Packing Material Store": [
		("PKG-BELLY", 3100), ("PKG-PVC-BAG", 1050), ("PKG-INSERT", 1050), ("PKG-CARTON-L", 300),
	],
}
VC_PURCHASE = {"supplier": "Sindh Cotton Ginners", "item": "VC-RAW", "qty": 5000, "rate": 520,
	"warehouse": "Virgin Cotton Store", "qi": {"Trash %": 2.2, "Moisture %": 7.2, "Avg Fiber Length (mm)": 29}}

SO_TWL = {"customer": "Nordic Home AB", "po_no": "DEMO-SO-TWL", "delivery_day": 20 + HT_OFFSET,
	"items": [("TWL-SET-3PC", 3000, 2400)]}
SO_BED = {"customer": "Home Comforts UK", "po_no": "DEMO-SO-BED", "delivery_day": 21 + HT_OFFSET,
	"items": [("BED-SET-KING", 1000, 5500)]}

YARN_PER_KG = 1.136
SPINNING = [("YRN-G-16NE-CT", 680), ("YRN-P-12NE-CT", 1360), ("YRN-W-20NE-CT", 680), ("YRN-30NE-CT", 1200)]
SPIN_OPERATOR = "OP-SP-01"

TERRY = {"qty": 2660, "kg_per_shift": 1330, "shifts": ["A", "B"], "looms": [f"TL-{i:03d}" for i in range(1, 17)],
	"transfer": [("YRN-G-16NE-CT", 678.3), ("YRN-P-12NE-CT", 1356.6), ("YRN-W-20NE-CT", 678.3)],
	"qi": {"GSM": 503, "Pile Height (mm)": 5}, "pile_height_mm": 5, "gsm": 503}
PROCESSING = {"qty": 2500, "recipe": "DR-TWL-WHT", "grey_kg": 2660, "operator": "OP-FD-01",
	# H2O2 4 % over recipe (35 g/kg → 36.4 g/kg actual)
	"chemicals": [("CHM-H2O2", 96.82), ("CHM-CAU", 53.2), ("CHM-WET", 5.32), ("CHM-OBA", 7.98), ("CHM-SOFT", 39.9)],
	"qi": {"Whiteness Index": 152, "Absorbency (sec)": 3, "GSM after processing": 506}}
FLAT = {"qty": 4350, "m_per_shift": 2175, "shifts": ["A", "B"], "looms": [f"FL-{i:03d}" for i in range(1, 13)],
	"transfer": [("YRN-30NE-CT", 1174.5)]}
PRINTING = {"qty": 4220, "recipe": "DR-PRT-FLORA", "grey_m": 4346.6, "chemicals": [("CHM-PIG", 195.6), ("CHM-SOFT", 21.73)],
	"qi": {"Print Registration Fault (count/100m)": 2, "Colour Fastness Wash (grade)": 4, "Width (inch)": 110}}

CTP_WO_QTY = 3080
# item: (fabric issued, avg sample weight kg, pieces cut, A, seconds, seconds kg, rags kg, cutting waste kg, line)
TOWEL_CTP = {
	"TWL-BATH-70140": (1555.4, 0.497, 3065, 3010, 55, 27.0, 12.0, 20.4, "CTP-CC-01"),
	"TWL-HAND-5090": (714.56, 0.231, 3065, 3015, 50, 11.5, 5.0, 9.0, "CTP-CC-01"),
	"TWL-FACE-3030": (144.76, 0.044, 3065, 3020, 45, 2.0, 1.5, 2.5, "CTP-CC-01"),
}
# item: (WO qty, fabric issued m, pieces cut, A, seconds, cutting waste kg, line)
SHEET_CTP = {
	"SHT-FLAT-KING": (1020, 2907.0, 1020, 1012, 8, 6.0, "CTP-SL-01"),
	"PC-STD": (2040, 1264.8, 2040, 2025, 15, 3.0, "CTP-SL-02"),
}

TOWEL_SET = {"qty": 3000, "transfer": [("TWL-BATH-70140", 3000), ("TWL-HAND-5090", 3000), ("TWL-FACE-3030", 3000)],
	"packing": [("PKG-BELLY", 3000)]}
BED_SET = {"qty": 1000, "transfer": [("SHT-FLAT-KING", 1000), ("PC-STD", 2000)],
	"packing": [("PKG-PVC-BAG", 1000), ("PKG-INSERT", 1000)]}

CARTONS = {
	"TWL-SET-3PC": {"so": "DEMO-SO-TWL", "net_kg_per_unit": 0, "dims": (60, 40, 40)},
	"BED-SET-KING": {"so": "DEMO-SO-BED", "net_kg_per_unit": 2.35, "dims": (60, 40, 45)},
}
AQL = {"Major Defects Found (sample 80, Ac 5)": 2}
SECONDS_SALE = {"customer": "Local Waste Buyer", "items": [("TWL-SECONDS", "Seconds Store", 450),
	("WST-RAGS", "Waste Store", 80), ("WST-CTP", "Waste Store", 60)]}


def loom_rows(looms: list[str], total: float, field: str, seed: int, weavers: list[str]) -> list[dict]:
	"""Efficiency 80–90 %; output scaled so the shift totals exactly `total` (kg for terry, m for flat)."""
	rng = random.Random(seed)
	rows = []
	for i, loom in enumerate(looms):
		eff = round(rng.uniform(80, 90), 1)
		rows.append({"loom": loom, "weaver": weavers[i % len(weavers)], "rpm": rng.choice([450, 480, 500]),
			"picks_per_inch": 40, "efficiency_pct": eff, "warp_breaks": rng.randint(2, 8),
			"weft_breaks": rng.randint(3, 12), "stop_minutes": rng.randint(10, 55), "_w": eff})
	weight = sum(r["_w"] for r in rows)
	values = [round(r["_w"] * total / weight, 2) for r in rows]
	values[-1] = round(total - sum(values[:-1]), 2)
	for r, v in zip(rows, values):
		r[field] = v
		r.pop("_w")
	return rows


def weight_samples(avg: float, n: int = 20, seed: int = 7) -> list[dict]:
	"""n samples (±2.5 %) whose mean is exactly `avg`."""
	rng = random.Random(seed)
	values = [round(avg * rng.uniform(0.975, 1.025), 4) for _ in range(n)]
	values[-1] = round(avg * n - sum(values[:-1]), 4)
	return [{"sample_no": i + 1, "weight_kg": v} for i, v in enumerate(values)]
