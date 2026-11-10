"""Denim master data (Part B §3–4). Pure data; applied by `textile_mill.setup.masters`."""

COMPANY = "Demo Textile Mills (Pvt) Ltd"
ABBR = "DDM"

ACCOUNTS = [
	# account_name, parent (without abbr), root_type, account_type
	("Utilities Absorbed", "Indirect Expenses", "Expense", "Expenses Included In Valuation"),
	("Electricity Expense", "Indirect Expenses", "Expense", ""),
	("Gas & Steam Expense", "Indirect Expenses", "Expense", ""),
	("Water Expense", "Indirect Expenses", "Expense", ""),
	("Waste Sales", "Direct Income", "Income", "Income Account"),
	("Subcontracting Charges", "Direct Expenses", "Expense", ""),
]

# warehouse group -> [(warehouse, inventory status)]
WAREHOUSES = {
	"DDM Stores": [
		("Cotton Waste Store", "Usable"),
		("Virgin Cotton Store", "Usable"),
		("Chemicals & Dyes Store", "Usable"),
		("Trims Store", "Usable"),
		("QC Hold", "QC Hold"),
	],
	"Recycling": [("Recycling WIP", "WIP"), ("Recycled Fiber Store", "Usable")],
	"Fiber Dyeing": [("Fiber Dyeing WIP", "WIP"), ("Dyed Fiber Store", "Usable")],
	"Spinning": [("Spinning WIP", "WIP"), ("Yarn Store", "Usable")],
	"Indigo": [("Indigo WIP", "WIP"), ("Beam Store", "Usable")],
	"Weaving": [("Weaving WIP", "WIP"), ("Grey Fabric Store", "Usable")],
	"Finishing": [
		("Finishing WIP", "WIP"),
		("Finished Lot Store", "QC Hold"),
		("Fabric A Store", "Usable"),
		("Fabric B Store", "B-Grade"),
		("Fabric Rejected Store", "Rejected"),
	],
	"Garments": [
		("Cutting WIP", "WIP"),
		("Stitching WIP", "WIP"),
		("Unwashed Garment Store", "Usable"),
		("Garment FG Store", "Usable"),
	],
	"Waste": [("Waste Store", "Waste")],
	"Subcontractor": [("Clean Wash Co.", "At Subcontractor")],
}

UOMS = {"Kg": 0, "Meter": 0, "Nos": 1, "Cone": 0, "Gram": 0, "Set": 1, "Dozen": 1, "Carton": 1}

# ERPNext ships "Raw Material", "Sub Assemblies", "Products", "Services" root groups.
ITEM_GROUPS = [
	("Cotton Waste", "Raw Material"),
	("Virgin Cotton", "Raw Material"),
	("Chemicals & Dyes", "Raw Material"),
	("Trims", "Raw Material"),
	("Packing Material", "Raw Material"),
	("Fiber", "Sub Assemblies"),
	("Yarn", "Sub Assemblies"),
	("Fabric", "Sub Assemblies"),
	("Garment WIP", "Sub Assemblies"),
	("Finished Fabric", "Products"),
	("Garments", "Products"),
	("Home Textile", "Products"),
	("Waste", "All Item Groups"),
]

SUPPLIERS = [
	("Karachi Textile Waste Traders", "Raw Material"),
	("Sindh Cotton Ginners", "Raw Material"),
	("ChemDye Pakistan", "Raw Material"),
	("Accessories Hub", "Raw Material"),
	("Clean Wash Co.", "Services"),
]
CUSTOMERS = ["Urban Threads LLC", "Lahore Fashion Fabrics"]

EMPLOYEES = ["OP-RC-01", "OP-FD-01", "OP-SP-01", "OP-IND-01", *[f"WEAVER-{i:02d}" for i in range(1, 9)], "QA-01", "CUT-01"]

SHIFTS = [("A", "07:00:00", "15:00:00"), ("B", "15:00:00", "23:00:00"), ("C", "23:00:00", "07:00:00")]
SHADES = [
	("SH-BLK-01", "Jet Black", "Fiber Dyeing", "#111111"),
	("SH-IND-DK", "Indigo Dark", "Indigo Dyeing", "#1f2a5c"),
]
DEFECT_TYPES = [
	("SLB", "Slub", "Weft"),
	("MPK", "Mispick", "Weft"),
	("BEN", "Broken End", "Warp"),
	("STN", "Stain", "Dyeing"),
	("HOL", "Hole", "Finishing"),
	("SHD", "Shade Bar", "Dyeing"),
	("CRS", "Crease Mark", "Finishing"),
]

# fmt: off
# code, name, group, uom, batch_series, default warehouse, buy rate, sell rate, stage, extra
ITEMS = [
	("CW-PRE", "Cotton Waste - Pre-Consumer", "Cotton Waste", "Kg", "CW-.YY.-.#####", "Cotton Waste Store", 180, 0, "Raw", {}),
	("CW-POST", "Cotton Waste - Post-Consumer", "Cotton Waste", "Kg", "CW-.YY.-.#####", "Cotton Waste Store", 140, 0, "Raw", {}),
	("VC-RAW", "Virgin Cotton Lint", "Virgin Cotton", "Kg", "VC-.YY.-.#####", "Virgin Cotton Store", 520, 0, "Raw", {}),
	("RF-PRE-A", "Recycled Fiber Grade A", "Fiber", "Kg", "RF-.YY.-.#####", "Recycled Fiber Store", 0, 0, "Cotton Recycling", {}),
	("DF-BLK", "Dyed Fiber Jet Black", "Fiber", "Kg", "DF-.YY.-.#####", "Dyed Fiber Store", 0, 0, "Fiber Dyeing", {"dm_shade": "SH-BLK-01"}),
	("YRN-W-10NE-60R", "Grey Warp Yarn 10 Ne OE (60% Recycled / 40% Cotton)", "Yarn", "Kg", "YL-.YY.-.#####", "Yarn Store", 0, 0, "Spinning",
		{"dm_yarn_count_ne": 10, "dm_blend_composition": "60% Recycled / 40% Cotton"}),
	("YRN-F-16NE-BLK", "Dyed Weft Yarn 16 Ne Ring (Black Melange)", "Yarn", "Kg", "YL-.YY.-.#####", "Yarn Store", 0, 0, "Spinning",
		{"dm_yarn_count_ne": 16, "dm_blend_composition": "28% Dyed Fiber / 44% Recycled / 28% Cotton"}),
	("IWY-10NE-IND", "Indigo Warp Yarn 10 Ne (Indigo Dark)", "Yarn", "Kg", "IND-.YY.-.#####", "Beam Store", 0, 0, "Indigo Dyeing",
		{"dm_yarn_count_ne": 10, "dm_shade": "SH-IND-DK"}),
	("GF-DM1150", "Grey Denim 11.5 oz 3/1 RHT 64\"", "Fabric", "Meter", "GR-.YY.-.#####", "Grey Fabric Store", 0, 0, "Weaving",
		{"dm_fabric_construction": "3/1 RHT, 10x16, 72x44", "dm_width_inch": 64, "dm_weight_oz": 11.5}),
	("FF-DM1150", "Finished Denim 11.5 oz Lot (Pre-Inspection)", "Fabric", "Meter", "FL-.YY.-.#####", "Finished Lot Store", 0, 0, "Finishing",
		{"dm_width_inch": 64, "dm_weight_oz": 11.5, "dm_target_gsm": 390}),
	("FF-DM1150-A", "Finished Denim 11.5 oz 64\" - A Grade", "Finished Fabric", "Meter", "ROLL-.YY.-.#####", "Fabric A Store", 0, 1100, "Finishing",
		{"dm_width_inch": 64, "dm_weight_oz": 11.5, "dm_target_gsm": 390}),
	("FF-DM1150-B", "Finished Denim 11.5 oz 64\" - B Grade", "Finished Fabric", "Meter", "ROLL-.YY.-.#####", "Fabric B Store", 0, 700, "Finishing", {}),
	("FF-DM1150-R", "Finished Denim - Rejected", "Finished Fabric", "Meter", "ROLL-.YY.-.#####", "Fabric Rejected Store", 0, 200, "Finishing", {}),
	("WST-HARD", "Hard Waste (Recycling)", "Waste", "Kg", None, "Waste Store", 40, 40, "Waste", {}),
	("WST-SOFT", "Soft Waste (Spinning)", "Waste", "Kg", None, "Waste Store", 90, 90, "Waste", {}),
	("WST-FAB", "Fabric Waste / Thrums", "Waste", "Kg", None, "Waste Store", 30, 30, "Waste", {}),
	("CHM-IND", "Indigo Dye (Synthetic)", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 3800, 0, "Raw", {}),
	("CHM-HYD", "Sodium Hydrosulphite", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 450, 0, "Raw", {}),
	("CHM-CAU", "Caustic Soda", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 160, 0, "Raw", {}),
	("CHM-WET", "Wetting Agent", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 600, 0, "Raw", {}),
	("CHM-SIZE", "Sizing Agent", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 400, 0, "Raw", {}),
	("CHM-SBLK", "Sulphur Black", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 900, 0, "Raw", {}),
	("CHM-NAS", "Sodium Sulphide", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 300, 0, "Raw", {}),
	("CHM-SODA", "Soda Ash", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 120, 0, "Raw", {}),
	("CHM-FIN", "Finishing Softener", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 700, 0, "Raw", {}),
	("TRM-ZIP", "Metal Zipper 7\"", "Trims", "Nos", None, "Trims Store", 35, 0, "Raw", {}),
	("TRM-BTN", "Shank Button", "Trims", "Nos", None, "Trims Store", 18, 0, "Raw", {}),
	("TRM-RVT", "Rivet", "Trims", "Nos", None, "Trims Store", 4, 0, "Raw", {}),
	("TRM-LBL", "Woven Label", "Trims", "Nos", None, "Trims Store", 10, 0, "Raw", {}),
	("TRM-THR", "Sewing Thread Cone 5000m", "Trims", "Cone", None, "Trims Store", 650, 0, "Raw", {}),
	("TRM-POCK", "Pocketing Fabric", "Trims", "Meter", None, "Trims Store", 220, 0, "Raw", {}),
	("PKG-POLY", "Polybag", "Trims", "Nos", None, "Trims Store", 8, 0, "Raw", {}),
]
# fmt: on

SERVICE_ITEMS = [("SRV-WASH", "Denim Stone Wash Service", 120, "Garments")]

GARMENT_SIZES = ["30", "32", "34", "36"]
GARMENT_TEMPLATES = [
	# code, name, group, default warehouse, sell rate, subcontracted FG
	("JNS-SLIM-UW", "Slim 5-Pocket Jeans - Unwashed", "Garment WIP", "Unwashed Garment Store", 0, 0),
	("JNS-SLIM-SW", "Slim 5-Pocket Jeans - Stone Wash", "Garments", "Garment FG Store", 3200, 1),
]

QI_TEMPLATES = {
	"QIT-CW": [("Trash %", 0, 8), ("Moisture %", 0, 9), ("Avg Fiber Length (mm)", 14, 40)],
	"QIT-RF": [("Avg Fiber Length (mm)", 16, 40), ("Neps per gram", 0, 400), ("Trash %", 0, 3)],
	"QIT-DF": [("Delta E (vs standard)", 0, 1.0), ("Wash Fastness (grade)", 3, 5)],
	"QIT-YRN-10": [("Actual Count (Ne)", 9.8, 10.2), ("Count CV %", 0, 2.5), ("CSP", 1700, 9999)],
	"QIT-YRN-16": [("Actual Count (Ne)", 15.7, 16.3), ("Count CV %", 0, 2.5), ("IPI (per km)", 0, 300)],
	"QIT-IND": [("Delta E (vs standard)", 0, 1.0), ("Rubbing Fastness Dry (grade)", 3, 5), ("Size Pick-up %", 10, 14)],
	"QIT-FF": [
		("GSM", 380, 400),
		("Width (inch)", 63, 65),
		("Shrinkage Warp %", 0, 3),
		("Shrinkage Weft %", 0, 3),
		("Skew %", 0, 4),
	],
	"QIT-JNS": [("Major Defects Found", 0, 7), ("Waist Measurement Deviation (cm)", 0, 1)],
}
ITEM_QI = {
	"CW-PRE": ("QIT-CW", "purchase"),
	"CW-POST": ("QIT-CW", "purchase"),
	"VC-RAW": ("QIT-CW", "purchase"),
}

# workstation, type, hour rate, stage, rated output/h, output uom
WORKSTATIONS = [
	("RCY-LINE-01", "Recycling Line", 4500, "Cotton Recycling", 500, "Kg"),
	("BR-CARD-01", "Blowroom & Carding", 6000, "Spinning", 450, "Kg"),
	("OE-01", "OE Rotor Spinning", 3000, "Spinning", 220, "Kg"),
	("OE-02", "OE Rotor Spinning", 3000, "Spinning", 220, "Kg"),
	*[(f"RF-{i:02d}", "Ring Frame", 2500, "Spinning", 90, "Kg") for i in range(1, 7)],
	("FD-01", "Loose Fiber Dyeing", 5000, "Fiber Dyeing", 300, "Kg"),
	("FD-02", "Loose Fiber Dyeing", 5000, "Fiber Dyeing", 300, "Kg"),
	("WRP-01", "Ball Warping", 2000, "Indigo Dyeing", 1300, "Kg"),
	("IRR-01", "Indigo Rope Dyeing Range", 18000, "Indigo Dyeing", 1300, "Kg"),
	("LCB-01", "Long Chain Beamer", 3000, "Indigo Dyeing", 1300, "Kg"),
	("SZ-01", "Sizing Machine", 6000, "Indigo Dyeing", 1300, "Kg"),
	("DRW-01", "Drawing-in", 1000, "Weaving", 2000, "Meter"),
	*[(f"LM-{i:03d}", "Air-jet Loom", 900, "Weaving", 20.8, "Meter") for i in range(1, 25)],
	("GI-01", "Grey Inspection", 1200, "Weaving", 1000, "Meter"),
	("STN-01", "Stenter / Singe-Mercerize", 7000, "Finishing", 1000, "Meter"),
	("SNF-01", "Sanforizer", 6500, "Finishing", 1100, "Meter"),
	("FI-01", "Final Fabric Inspection", 1200, "Finishing", 1000, "Meter"),
	("CUT-01", "Cutting Table", 1500, "Garments", 400, "Nos"),
	*[(f"SL-{i:02d}", "Sewing Line", 4000, "Garments", 100, "Nos") for i in range(1, 5)],
]

OPERATIONS = [
	"Waste Sorting & Opening", "Garnetting", "Fiber Loading", "Fiber Dyeing", "Hydro & Drying",
	"Blowroom & Carding", "OE Spinning", "Ring Spinning", "Winding", "Ball Warping", "Rope Indigo Dyeing",
	"Long Chain Beaming", "Sizing", "Drawing-in", "Weaving", "Grey Inspection", "Singe & Mercerize",
	"Sanforizing", "Cutting", "Stitching",
]

# Re-process operations (ERPNext corrective job cards need is_corrective_operation).
CORRECTIVE_OPERATIONS = [
	("Shade Correction Re-dip", "IRR-01"),
	("Fiber Re-dyeing", "FD-01"),
]

# stage, utility rate per output uom, uom
UTILITY_RATES = [
	("Cotton Recycling", 6, "Kg"),
	("Fiber Dyeing", 35, "Kg"),
	("Spinning", 55, "Kg"),
	("Indigo Dyeing", 40, "Kg"),
	("Weaving", 18, "Meter"),
	("Finishing", 22, "Meter"),
	("Garments", 15, "Nos"),
]

# lot item, grade, graded item, warehouse, relative sales value
GRADE_MAP = [
	("FF-DM1150", "A", "FF-DM1150-A", "Fabric A Store", 1100),
	("FF-DM1150", "B", "FF-DM1150-B", "Fabric B Store", 700),
	("FF-DM1150", "Rejected", "FF-DM1150-R", "Fabric Rejected Store", 200),
]

# ---------------------------------------------------------------- BOMs (Part B §4.8)
# item, qty, [(rm, qty)], [(scrap, qty)], [(operation, workstation, minutes)], qi template
BOMS = [
	("RF-PRE-A", 850, [("CW-PRE", 1000)], [("WST-HARD", 75)],
		[("Waste Sorting & Opening", "RCY-LINE-01", 60), ("Garnetting", "RCY-LINE-01", 60)], "QIT-RF"),
	("YRN-W-10NE-60R", 1000, [("RF-PRE-A", 682), ("VC-RAW", 454)], [("WST-SOFT", 100)],
		[("Blowroom & Carding", "BR-CARD-01", 180), ("OE Spinning", "OE-01", 600)], "QIT-YRN-10"),
	("YRN-F-16NE-BLK", 1000, [("DF-BLK", 320), ("RF-PRE-A", 500), ("VC-RAW", 316)], [("WST-SOFT", 100)],
		[("Blowroom & Carding", "BR-CARD-01", 180), ("Ring Spinning", "RF-01", 840), ("Winding", "RF-01", 120)],
		"QIT-YRN-16"),
	("GF-DM1150", 1000, [("IWY-10NE-IND", 340), ("YRN-F-16NE-BLK", 280)], [("WST-FAB", 8)],
		[("Drawing-in", "DRW-01", 30), ("Weaving", "LM-001", 3360), ("Grey Inspection", "GI-01", 60)], None),
	("FF-DM1150", 1000, [("GF-DM1150", 1050), ("CHM-FIN", 10)], [],
		[("Singe & Mercerize", "STN-01", 120), ("Sanforizing", "SNF-01", 90)], "QIT-FF"),
]

JEANS_FABRIC_PER_SIZE = {"30": 1.30, "32": 1.33, "34": 1.37, "36": 1.40}
JEANS_TRIMS = [("TRM-POCK", 0.25), ("TRM-ZIP", 1), ("TRM-BTN", 1), ("TRM-RVT", 6), ("TRM-LBL", 2), ("TRM-THR", 0.04)]
JEANS_OPS = [("Cutting", "CUT-01", 0.3), ("Stitching", "SL-01", 0.6)]

DYE_RECIPES = [
	{
		"name": "DR-BLK-001",
		"recipe_title": "Jet Black Sulphur - Recycled Fiber",
		"process_type": "Fiber Dyeing",
		"shade": "SH-BLK-01",
		"base_item": "RF-PRE-A",
		"output_item": "DF-BLK",
		"base_qty_kg": 1000,
		"expected_yield_pct": 97,
		"liquor_ratio": "1:8",
		"temperature_c": 90,
		"time_min": 240,
		"chemicals": [("CHM-SBLK", 60), ("CHM-NAS", 40), ("CHM-SODA", 20), ("CHM-WET", 2)],
	},
	{
		"name": "DR-IND-001",
		"recipe_title": "Indigo Dark - Rope Dyeing 10 Ne",
		"process_type": "Indigo Dyeing",
		"shade": "SH-IND-DK",
		"base_item": "YRN-W-10NE-60R",
		"output_item": "IWY-10NE-IND",
		"base_qty_kg": 1011,
		"expected_yield_pct": 98.91,
		"temperature_c": 28,
		"time_min": 180,
		"ph_min": 11.0,
		"ph_max": 11.8,
		"redox_min_mv": -820,
		"redox_max_mv": -760,
		"indigo_g_l_min": 2.0,
		"indigo_g_l_max": 2.6,
		"chemicals": [("CHM-IND", 20), ("CHM-HYD", 25), ("CHM-CAU", 20), ("CHM-WET", 2), ("CHM-SIZE", 80)],
	},
]
