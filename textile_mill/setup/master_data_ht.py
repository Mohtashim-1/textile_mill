"""Home Textile master data (Part D §D1–D5). Pure data; applied by `textile_mill.setup.masters_ht`."""

WAREHOUSES = {
	"Home Textile": [
		("HT Yarn Store", "Usable"),
		("Beam Store HT", "Usable"),
		("Terry Weaving WIP", "WIP"),
		("Grey Terry Store", "Usable"),
		("Flat Weaving WIP", "WIP"),
		("Grey Sheeting Store", "Usable"),
		("Processing WIP", "WIP"),
		("Processed Terry Store", "Usable"),
		("Printing WIP", "WIP"),
		("Processed Sheeting Store", "Usable"),
		("CTP WIP", "WIP"),
		("Towel Pieces Store", "Usable"),
		("Sheet Pieces Store", "Usable"),
		("Seconds Store", "B-Grade"),
		("Set Assembly WIP", "WIP"),
		("HT FG Store", "Usable"),
		("Packing Material Store", "Usable"),
	],
	"Subcontractor": [("Stitch Art Embroidery", "At Subcontractor"), ("Prime Prints", "At Subcontractor")],
}

ITEM_GROUPS = [("Home Textile WIP", "Sub Assemblies")]

SUPPLIERS = [("Stitch Art Embroidery", "Services"), ("Prime Prints", "Services")]
CUSTOMERS = ["Nordic Home AB", "Home Comforts UK"]


def _piece(target_kg: float, size: str) -> dict:
	return {"dm_target_weight_kg": target_kg, "dm_weight_tolerance_pct": 5, "dm_size_cm": size, "dm_target_gsm": 500}


# fmt: off
# code, name, group, uom, batch_series, default warehouse, buy/valuation rate, sell rate, stage, extra
ITEMS = [
	("YRN-G-16NE-CT", "Ground Yarn 16 Ne Combed Cotton", "Yarn", "Kg", "YL-.YY.-.#####", "HT Yarn Store", 0, 0, "Spinning",
		{"dm_yarn_count_ne": 16, "dm_blend_composition": "100% Cotton (combed)"}),
	("YRN-P-12NE-CT", "Pile Yarn 12 Ne Ring Cotton (Low Twist)", "Yarn", "Kg", "YL-.YY.-.#####", "HT Yarn Store", 0, 0, "Spinning",
		{"dm_yarn_count_ne": 12, "dm_blend_composition": "100% Cotton"}),
	("YRN-W-20NE-CT", "Weft Yarn 20 Ne Cotton", "Yarn", "Kg", "YL-.YY.-.#####", "HT Yarn Store", 0, 0, "Spinning",
		{"dm_yarn_count_ne": 20, "dm_blend_composition": "100% Cotton"}),
	("YRN-30NE-CT", "Sheeting Yarn 30 Ne Combed", "Yarn", "Kg", "YL-.YY.-.#####", "HT Yarn Store", 0, 0, "Spinning",
		{"dm_yarn_count_ne": 30, "dm_blend_composition": "100% Cotton (combed)"}),
	("GT-500", "Grey Terry 500 GSM", "Fabric", "Kg", "GT-.YY.-.#####", "Grey Terry Store", 0, 0, "Terry Weaving",
		{"dm_target_gsm": 500}),
	("PT-500-WHT", "Processed Terry 500 GSM White", "Fabric", "Kg", "PT-.YY.-.#####", "Processed Terry Store", 0, 0, "Processing",
		{"dm_target_gsm": 500}),
	("GS-200TC", "Grey Sheeting 200 TC 110\"", "Fabric", "Meter", "GS-.YY.-.#####", "Grey Sheeting Store", 0, 0, "Flat Weaving",
		{"dm_width_inch": 110, "dm_fabric_construction": "200 TC plain"}),
	("PS-200TC-PRT", "Printed Sheeting 200 TC (Design FLORA)", "Fabric", "Meter", "PS-.YY.-.#####", "Processed Sheeting Store", 0, 0,
		"Printing", {"dm_width_inch": 110, "dm_design": "FLORA"}),
	("TWL-BATH-70140", "Bath Towel 70x140 White 500 GSM", "Home Textile WIP", "Nos", "TP-.YY.-.#####", "Towel Pieces Store", 0, 0,
		"Cut-to-Piece", _piece(0.490, "70x140")),
	("TWL-HAND-5090", "Hand Towel 50x90 White 500 GSM", "Home Textile WIP", "Nos", "TP-.YY.-.#####", "Towel Pieces Store", 0, 0,
		"Cut-to-Piece", _piece(0.225, "50x90")),
	("TWL-FACE-3030", "Face Towel 30x30 White 500 GSM", "Home Textile WIP", "Nos", "TP-.YY.-.#####", "Towel Pieces Store", 0, 0,
		"Cut-to-Piece", _piece(0.045, "30x30")),
	("TWL-SECONDS", "Towel Seconds (mixed)", "Home Textile", "Kg", None, "Seconds Store", 450, 450, "Cut-to-Piece", {}),
	("WST-RAGS", "Terry Rags", "Waste", "Kg", None, "Waste Store", 80, 80, "Waste", {}),
	("TWL-SET-3PC", "Towel Set 3-pc (Bath+Hand+Face) White", "Home Textile", "Set", "TS-.YY.-.#####", "HT FG Store", 0, 2400,
		"Set Assembly", {}),
	("SHT-FLAT-KING", "Flat Sheet King FLORA", "Home Textile WIP", "Nos", "SP-.YY.-.#####", "Sheet Pieces Store", 0, 0,
		"Cut-to-Piece", {"dm_design": "FLORA", "dm_size_cm": "275x290"}),
	("PC-STD", "Pillow Cover Standard FLORA", "Home Textile WIP", "Nos", "SP-.YY.-.#####", "Sheet Pieces Store", 0, 0,
		"Cut-to-Piece", {"dm_design": "FLORA", "dm_size_cm": "50x75"}),
	("BED-SET-KING", "Bed Sheet Set King FLORA (1 sheet + 2 PC)", "Home Textile", "Set", "BS-.YY.-.#####", "HT FG Store", 0, 5500,
		"Set Assembly", {"dm_design": "FLORA"}),
	("WST-CTP", "CTP Cutting Waste", "Waste", "Kg", None, "Waste Store", 60, 60, "Waste", {}),
	("CHM-H2O2", "Hydrogen Peroxide 50%", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 220, 0, "Raw", {}),
	("CHM-OBA", "Optical Brightener", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 1500, 0, "Raw", {}),
	("CHM-SOFT", "Silicone Softener", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 900, 0, "Raw", {}),
	("CHM-PIG", "Pigment Print Paste (FLORA set)", "Chemicals & Dyes", "Kg", "CHM-.YY.-.#####", "Chemicals & Dyes Store", 1200, 0,
		"Raw", {}),
	("TRM-HEM-THR", "Hemming Thread Cone", "Trims", "Cone", None, "Trims Store", 500, 0, "Raw", {}),
	("TRM-CARE-LBL", "Care Label (customer-specific)", "Trims", "Nos", None, "Trims Store", 3, 0, "Raw", {}),
	("TRM-LOOP", "Hanging Loop Tape", "Trims", "Meter", None, "Trims Store", 15, 0, "Raw", {}),
	("PKG-BELLY", "Belly Band (set)", "Packing Material", "Nos", None, "Packing Material Store", 12, 0, "Raw", {}),
	("PKG-PVC-BAG", "PVC Zip Bag (bed set)", "Packing Material", "Nos", None, "Packing Material Store", 45, 0, "Raw", {}),
	("PKG-INSERT", "Cardboard Insert", "Packing Material", "Nos", None, "Packing Material Store", 10, 0, "Raw", {}),
	("PKG-CARTON-L", "Export Carton Large", "Packing Material", "Nos", None, "Packing Material Store", 180, 0, "Raw", {}),
]
# fmt: on

SERVICE_ITEMS = [("SRV-EMB", "Embroidery Service (per piece)", 25, "Cut-to-Piece")]

# customer item codes (standard Item Customer Detail) and Customer Label Spec rows
CUSTOMER_ITEMS = {
	"TWL-SET-3PC": [("Nordic Home AB", "NH-TS3-WHT500", "7350012345671", 24, "NORDIC HOME AB\nGOTHENBURG, SWEDEN\nMADE IN PAKISTAN")],
	"BED-SET-KING": [("Home Comforts UK", "HC-BSK-FLORA", "5012345678900", 10, "HOME COMFORTS UK\nMANCHESTER DC\nMADE IN PAKISTAN")],
}

QI_TEMPLATES = {
	"QIT-TERRY-GREY": [("GSM", 480, 520), ("Pile Height (mm)", 4, 6)],
	"QIT-TERRY-PROC": [("Whiteness Index", 140, 999), ("Absorbency (sec)", 0, 5), ("GSM after processing", 490, 525)],
	"QIT-SHEET-PRINT": [
		("Print Registration Fault (count/100m)", 0, 3),
		("Colour Fastness Wash (grade)", 3.5, 5),
		("Width (inch)", 108, 112),
	],
	"QIT-SET-AQL": [("Major Defects Found (sample 80, Ac 5)", 0, 5)],
}
ITEM_QI = {
	"TWL-SET-3PC": ("QIT-SET-AQL", "delivery"),
	"BED-SET-KING": ("QIT-SET-AQL", "delivery"),
}

# workstation, type, hour rate, stage, rated output/h, output uom
WORKSTATIONS = [
	("WRP-HT-01", "Warping (HT)", 2000, "Terry Weaving", 400, "Kg"),
	("SZ-HT-01", "Sizing (HT)", 6000, "Terry Weaving", 450, "Kg"),
	*[(f"TL-{i:03d}", "Terry Loom", 1100, "Terry Weaving", 9, "Kg") for i in range(1, 17)],
	*[(f"FL-{i:03d}", "Flat Wide Loom", 1000, "Flat Weaving", 18, "Meter") for i in range(1, 13)],
	("SFT-01", "Soft-flow Dyeing/Bleaching", 6000, "Processing", 400, "Kg"),
	("TMB-01", "Tumble Dryer", 3000, "Processing", 300, "Kg"),
	("RTP-01", "Rotary Print Machine", 9000, "Printing", 1500, "Meter"),
	("CUR-01", "Curing/Stenter (HT)", 7000, "Printing", 1200, "Meter"),
	("CTP-LC-01", "Length Cutter", 1500, "Cut-to-Piece", 1200, "Nos"),
	("CTP-CC-01", "Cross Cutter & Hemmer", 2500, "Cut-to-Piece", 600, "Nos"),
	*[(f"CTP-SL-{i:02d}", "Home Textile Sewing Line", 3500, "Cut-to-Piece", 250, "Nos") for i in range(1, 4)],
	("WCHK-01", "Weighing & Inspection Table", 800, "Cut-to-Piece", 800, "Nos"),
	# Set work orders post their output under Set Assembly, so the line is rated against that stage.
	("PCK-01", "Packing Line", 1500, "Set Assembly", 300, "Set"),
]

OPERATIONS = [
	"Warping", "Terry Weaving", "Flat Weaving", "Soft-flow Bleaching", "Tumble Drying", "Rotary Printing", "Curing",
	"Length Cutting", "Cross Cutting & Hemming", "Weighing & Inspection", "Packing",
]

# stage, utility rate per output uom, uom
UTILITY_RATES = [
	("Terry Weaving", 30, "Kg"),
	("Flat Weaving", 14, "Meter"),
	("Processing", 45, "Kg"),
	("Printing", 12, "Meter"),
	("Cut-to-Piece", 2, "Nos"),
	("Set Assembly", 3, "Set"),
]

SPIN_OPS = [("Blowroom & Carding", "BR-CARD-01", 180), ("Ring Spinning", "RF-01", 840)]
CTP_TOWEL_OPS = [("Length Cutting", "CTP-LC-01", 0.05), ("Cross Cutting & Hemming", "CTP-CC-01", 0.10),
	("Weighing & Inspection", "WCHK-01", 0.075)]
CTP_SHEET_OPS = [("Length Cutting", "CTP-LC-01", 0.05), ("Stitching", "CTP-SL-01", 0.30)]

# fmt: off
# item, qty, [(rm, qty)], [(scrap, qty)], [(operation, workstation, minutes)], qi template — in dependency order
BOMS = [
	*[(yarn, 1000, [("VC-RAW", 1136)], [("WST-SOFT", 100)], SPIN_OPS, None)
		for yarn in ("YRN-G-16NE-CT", "YRN-P-12NE-CT", "YRN-W-20NE-CT", "YRN-30NE-CT")],
	("GT-500", 1000, [("YRN-G-16NE-CT", 255), ("YRN-P-12NE-CT", 510), ("YRN-W-20NE-CT", 255)], [("WST-RAGS", 10)],
		[("Warping", "WRP-HT-01", 120), ("Sizing", "SZ-HT-01", 60), ("Terry Weaving", "TL-001", 6700)], "QIT-TERRY-GREY"),
	("DR-TWL-WHT", None, None, None, None, None),
	("TWL-BATH-70140", 1, [("PT-500-WHT", 0.505), ("TRM-HEM-THR", 0.004), ("TRM-CARE-LBL", 1), ("TRM-LOOP", 0.08)], [],
		CTP_TOWEL_OPS, None),
	("TWL-HAND-5090", 1, [("PT-500-WHT", 0.232), ("TRM-HEM-THR", 0.003), ("TRM-CARE-LBL", 1), ("TRM-LOOP", 0.08)], [],
		CTP_TOWEL_OPS, None),
	("TWL-FACE-3030", 1, [("PT-500-WHT", 0.047), ("TRM-HEM-THR", 0.002), ("TRM-CARE-LBL", 1)], [], CTP_TOWEL_OPS, None),
	("TWL-SET-3PC", 1, [("TWL-BATH-70140", 1), ("TWL-HAND-5090", 1), ("TWL-FACE-3030", 1), ("PKG-BELLY", 1)], [],
		[("Packing", "PCK-01", 0.2)], None),
	("GS-200TC", 1000, [("YRN-30NE-CT", 270)], [],
		[("Warping", "WRP-HT-01", 60), ("Sizing", "SZ-HT-01", 60), ("Flat Weaving", "FL-001", 3330)], None),
	("DR-PRT-FLORA", None, None, None, None, None),
	("SHT-FLAT-KING", 1, [("PS-200TC-PRT", 2.85), ("TRM-HEM-THR", 0.01), ("TRM-CARE-LBL", 1)], [], CTP_SHEET_OPS, None),
	("PC-STD", 1, [("PS-200TC-PRT", 0.62), ("TRM-HEM-THR", 0.005), ("TRM-CARE-LBL", 1)], [], CTP_SHEET_OPS, None),
	("BED-SET-KING", 1, [("SHT-FLAT-KING", 1), ("PC-STD", 2), ("PKG-PVC-BAG", 1), ("PKG-INSERT", 1)], [],
		[("Packing", "PCK-01", 0.3)], None),
]
# fmt: on

DYE_RECIPES = {
	"DR-TWL-WHT": {
		"name": "DR-TWL-WHT",
		"recipe_title": "Terry Bleach White 500 GSM",
		"process_type": "Processing",
		"basis_uom": "per kg",
		"base_item": "GT-500",
		"output_item": "PT-500-WHT",
		"base_qty_kg": 1064,
		"expected_yield_pct": 93.985,
		"liquor_ratio": "1:6",
		"temperature_c": 98,
		"time_min": 300,
		"chemicals": [("CHM-H2O2", 35), ("CHM-CAU", 20), ("CHM-WET", 2), ("CHM-OBA", 3), ("CHM-SOFT", 15)],
	},
	"DR-PRT-FLORA": {
		"name": "DR-PRT-FLORA",
		"recipe_title": "Pigment Print FLORA on 200 TC",
		"process_type": "Printing",
		"basis_uom": "per m",
		"base_item": "GS-200TC",
		"output_item": "PS-200TC-PRT",
		"base_qty_kg": 1030,
		"expected_yield_pct": 97.087,
		"temperature_c": 160,
		"time_min": 90,
		"chemicals": [("CHM-PIG", 45), ("CHM-SOFT", 5)],
	},
}
