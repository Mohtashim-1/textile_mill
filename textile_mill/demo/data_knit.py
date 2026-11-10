"""Knitting demo constants (Part E §E7). Day numbers are offsets from the knit start (denim D0 + K_OFFSET)."""

import random

K_OFFSET = 4  # K-01 posts on denim day 4

STORES = {
	"Spinning": ("Virgin Cotton Store", "Spinning WIP", "Knit Yarn Store"),
	"Knitting": ("Knit Yarn Store", "Knitting WIP", "Greige Knit Store"),
	"Knit Dyeing": ("Greige Knit Store", "Knit Dyeing WIP", "Dyed Knit Store"),
	"Knit Finishing": ("Dyed Knit Store", "Knit Finishing WIP", "Finished Knit Store"),
}

OPENING_STOCK = {
	"Chemicals & Dyes Store": [("CHM-RNAVY", 60), ("CHM-SALT", 80), ("CHM-SODA", 30), ("CHM-SOFT", 15)],
	"Trims Store": [("TRM-RIB-NAVY", 55), ("TRM-THR", 105), ("TRM-CARE-LBL", 5100)],
}
VC_PURCHASE = {"supplier": "Sindh Cotton Ginners", "item": "VC-RAW", "qty": 1500, "rate": 525,
	"warehouse": "Virgin Cotton Store", "qi": {"Trash %": 2.4, "Moisture %": 7.0, "Avg Fiber Length (mm)": 28.5}}

TSHIRT = "TSH-CREW-NAVY"
SO_TSH = {"customer": "Metro Retail (Pvt) Ltd", "po_no": "DEMO-SO-TSH", "delivery_day": 12 + K_OFFSET,
	"items": [(f"{TSHIRT}-{s}", q, 1200) for s, q in (("S", 833), ("M", 1667), ("L", 1667), ("XL", 833))]}

YARN_PER_KG = 1.136
SPINNING = ("YRN-K-30NE-CT", 1270)

KNITTING = {"qty": 1250, "yarn_kg": 1268.75, "machines": [f"CK-{i:02d}" for i in range(1, 21)],
	# (shift, day offset, posting time, kg) — shift C runs overnight and posts next morning
	"shifts": [("A", 2, "15:00:00", 420), ("B", 2, "23:00:00", 420), ("C", 3, "06:50:00", 410)]}

# two jet batches (JET capacity 1,000 kg each) → ~60 % machine load
DYEING = {"recipe": "DR-KNAVY", "batches": [(600, 630.25), (590, 619.75)],
	"chemicals_per_kg": [("CHM-RNAVY", 0.040), ("CHM-SALT", 0.060), ("CHM-SODA", 0.020)], "operator": "OP-FD-01"}

FINISHING = {"qty": 1165, "dyed_kg": 1190, "softener": 11.65, "operator": "OP-FD-01",
	"qi": {"GSM": 161, "Shrinkage %": 3.8, "Spirality %": 3.2}}

# 1:2:2:1 marker, 834 plies → 5,004 pieces (4 over-cut); 72" open width at 160 GSM
CUT_PLAN = {"marker_length_m": 4.70, "plies": 834, "end_bit_allowance_pct": 1,
	"ratio": [("S", 1), ("M", 2), ("L", 2), ("XL", 1)]}
STITCH_LINES = ["KSL-01", "KSL-02", "KSL-03"]


def knit_rows(machines: list[str], total: float, seed: int, operators: list[str]) -> list[dict]:
	"""Efficiency 80–90 %; ~20 kg rolls; kg scaled so the shift totals exactly `total`."""
	rng = random.Random(seed)
	rows = []
	for i, machine in enumerate(machines):
		eff = round(rng.uniform(80, 90), 1)
		rows.append({"machine": machine, "operator": operators[i % len(operators)], "dia_inch": 30, "gauge": 24,
			"stitch_length_mm": 2.8, "rpm": rng.choice([28, 30, 32]), "efficiency_pct": eff, "rolls_produced": 1,
			"defects_count": rng.choice([0, 0, 0, 1]), "stop_minutes": rng.randint(10, 45), "_w": eff})
	weight = sum(r["_w"] for r in rows)
	values = [round(r["_w"] * total / weight, 2) for r in rows]
	values[-1] = round(total - sum(values[:-1]), 2)
	for r, v in zip(rows, values):
		r["kg_produced"] = v
		r.pop("_w")
	return rows
