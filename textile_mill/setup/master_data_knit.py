"""Knitting master data (Part E §E1–E4). Pure data; applied by `textile_mill.setup.masters_knit`."""

WAREHOUSES = {
	"Knitting": [
		("Knit Yarn Store", "Usable"),
		("Knitting WIP", "WIP"),
		("Greige Knit Store", "Usable"),
		("Knit Dyeing WIP", "WIP"),
		("Dyed Knit Store", "Usable"),
		("Knit Finishing WIP", "WIP"),
		("Finished Knit Store", "Usable"),
		("Knit Cutting WIP", "WIP"),
		("Knit FG Store", "Usable"),
	],
}

CUSTOMERS = ["Metro Retail (Pvt) Ltd"]

TSHIRT_ATTRIBUTE = "T-Shirt Size"
TSHIRT_SIZES = ["S", "M", "L", "XL"]
# size: finished knit kg per piece (Part E §E4)
TSHIRT_FABRIC_KG = {"S": 0.20, "M": 0.22, "L": 0.24, "XL": 0.26}
TSHIRT_TRIMS = [("TRM-RIB-NAVY", 0.01), ("TRM-THR", 0.02), ("TRM-CARE-LBL", 1)]
TSHIRT_OPS = [("Cutting", "KCUT-01", 0.12), ("Stitching", "KSL-01", 0.75)]
# template, name, group, FG warehouse, sell rate
TSHIRT_TEMPLATE = ("TSH-CREW-NAVY", "Crew-neck T-Shirt Navy 160 GSM", "Garments", "Knit FG Store", 1200)

_GREIGE = {"dm_target_gsm": 160, "dm_machine_dia": 30, "dm_gauge": 24, "dm_stitch_length_mm": 2.8}

# fmt: off
# code, name, group, uom, batch_series, default warehouse, buy/valuation rate, sell rate, stage, extra
ITEMS = [
	("YRN-K-30NE-CT", "Knitting Yarn 30 Ne Combed Cotton", "Yarn", "Kg", "YL-.YY.-.#####", "Knit Yarn Store", 0, 0, "Spinning",
		{"dm_yarn_count_ne": 30, "dm_blend_composition": "100% Cotton (combed)"}),
	("GK-SJ-160", "Greige Single Jersey 160 GSM 30\" dia", "Fabric", "Kg", "GK-.YY.-.#####", "Greige Knit Store", 0, 0, "Knitting",
		_GREIGE),
	("DK-SJ-160-NAVY", "Dyed Single Jersey Navy", "Fabric", "Kg", "DK-.YY.-.#####", "Dyed Knit Store", 0, 0, "Knit Dyeing",
		{"dm_target_gsm": 160}),
	("FK-SJ-160-NAVY", "Finished Single Jersey Navy (compacted)", "Fabric", "Kg", "FK-.YY.-.#####", "Finished Knit Store", 0, 0,
		"Knit Finishing", {"dm_target_gsm": 160, "dm_width_inch": 72}),
	("CHM-RNAVY", "Reactive Navy (knit)", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 2400, 0, "Raw", {}),
	("CHM-SALT", "Glauber Salt", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 35, 0, "Raw", {}),
	("TRM-RIB-NAVY", "Rib 1x1 Navy (neck)", "Trims", "Kg", None, "Trims Store", 1400, 0, "Raw", {}),
]
# fmt: on

QI_TEMPLATES = {
	"QIT-KNIT-FIN": [("GSM", 155, 165), ("Shrinkage %", 0, 5), ("Spirality %", 0, 5)],
}

# workstation, type, hour rate, stage, rated output/h, output uom
WORKSTATIONS = [
	*[(f"CK-{i:02d}", "Circular Knitting Machine", 600, "Knitting", 3.0, "Kg") for i in range(1, 21)],
	("JET-01", "Jet Dyeing (Knit)", 8000, "Knit Dyeing", 125, "Kg"),
	("JET-02", "Jet Dyeing (Knit)", 8000, "Knit Dyeing", 125, "Kg"),
	("STN-K-01", "Open-width Stenter", 7000, "Knit Finishing", 250, "Kg"),
	("CMP-01", "Compactor", 3000, "Knit Finishing", 300, "Kg"),
	("KCUT-01", "Knit Cutting Table", 1200, "Knit Garments", 500, "Nos"),
	*[(f"KSL-{i:02d}", "Knit Sewing Line", 3500, "Knit Garments", 80, "Nos") for i in range(1, 4)],
]

OPERATIONS = ["Circular Knitting", "Jet Dyeing", "Open-width Stentering", "Compacting", "Cutting", "Stitching"]

# stage, utility rate per output uom, uom
UTILITY_RATES = [
	("Knitting", 12, "Kg"),
	("Knit Dyeing", 40, "Kg"),
	("Knit Finishing", 15, "Kg"),
	("Knit Garments", 4, "Nos"),
]

SPIN_OPS = [("Blowroom & Carding", "BR-CARD-01", 180), ("Ring Spinning", "RF-01", 840)]

# item, qty, [(rm, qty)], [(scrap, qty)], [(operation, workstation, minutes)], qi template — in dependency order
BOMS = [
	("YRN-K-30NE-CT", 1000, [("VC-RAW", 1136)], [("WST-SOFT", 100)], SPIN_OPS, None),
	# ≈ 333 machine-hours per 1,000 kg (3 kg/h per machine)
	("GK-SJ-160", 1000, [("YRN-K-30NE-CT", 1015)], [], [("Circular Knitting", "CK-01", 19980)], None),
	("DR-KNAVY", None, None, None, None, None),
	("FK-SJ-160-NAVY", 1000, [("DK-SJ-160-NAVY", 1020), ("CHM-SOFT", 10)], [],
		[("Open-width Stentering", "STN-K-01", 240), ("Compacting", "CMP-01", 200)], "QIT-KNIT-FIN"),
]

DYE_RECIPES = {
	"DR-KNAVY": {
		"name": "DR-KNAVY",
		"recipe_title": "Reactive Navy on Single Jersey 160",
		"process_type": "Knit Dyeing",
		"basis_uom": "per kg",
		"base_item": "GK-SJ-160",
		"output_item": "DK-SJ-160-NAVY",
		"base_qty_kg": 1050,
		"expected_yield_pct": 95.238,
		"liquor_ratio": "1:8",
		"temperature_c": 60,
		"time_min": 480,
		"chemicals": [("CHM-RNAVY", 40), ("CHM-SALT", 60), ("CHM-SODA", 20)],
	},
}
