"""Shared constants for the Textile Mill app."""

DENIM_STAGES: tuple[str, ...] = (
	"Cotton Recycling",
	"Fiber Dyeing",
	"Spinning",
	"Indigo Dyeing",
	"Weaving",
	"Finishing",
	"Garments",
)
HOME_TEXTILE_STAGES: tuple[str, ...] = (
	"Terry Weaving",
	"Flat Weaving",
	"Processing",
	"Printing",
	"Cut-to-Piece",
	"Set Assembly",
	"Packing",
)
KNIT_STAGES: tuple[str, ...] = ("Knitting", "Knit Dyeing", "Knit Finishing", "Knit Garments")

# Order matters: it is the Select option order everywhere a stage is stored.
PRODUCTION_STAGES: tuple[str, ...] = DENIM_STAGES + HOME_TEXTILE_STAGES + KNIT_STAGES
ITEM_STAGES: tuple[str, ...] = ("Raw",) + PRODUCTION_STAGES + ("Waste",)

BUSINESS_LINES: dict[str, tuple[str, ...]] = {
	"Denim": DENIM_STAGES,
	"Home Textile": ("Spinning",) + HOME_TEXTILE_STAGES,
	"Knitting": ("Spinning",) + KNIT_STAGES,
}

PLANTS: tuple[str, ...] = (
	"Plant-1 Spinning & Recycling",
	"Plant-2 Denim",
	"Plant-3 Garments",
	"Plant-4 Home Textile",
	"Plant-5 Knitting",
)
STAGE_PLANT: dict[str, str] = {
	"Cotton Recycling": PLANTS[0],
	"Fiber Dyeing": PLANTS[0],
	"Spinning": PLANTS[0],
	"Indigo Dyeing": PLANTS[1],
	"Weaving": PLANTS[1],
	"Finishing": PLANTS[1],
	"Garments": PLANTS[2],
	**{s: PLANTS[3] for s in HOME_TEXTILE_STAGES},
	**{s: PLANTS[4] for s in KNIT_STAGES},
}

# Stage -> cost center name (without company abbreviation suffix).
STAGE_COST_CENTER: dict[str, str] = {
	**{s: s for s in DENIM_STAGES},
	**{s: s for s in HOME_TEXTILE_STAGES if s != "Set Assembly"},
	"Set Assembly": "Packing",
	**{s: s for s in KNIT_STAGES},
}
COST_CENTERS: tuple[str, ...] = tuple(dict.fromkeys(list(STAGE_COST_CENTER.values()) + ["Utilities & Admin"]))

INVENTORY_STATUSES: tuple[str, ...] = (
	"Usable",
	"WIP",
	"QC Hold",
	"B-Grade",
	"Rejected",
	"Waste",
	"At Subcontractor",
	"In Transit",
)

# Item groups whose consumption is not "main material" in yield maths.
# Stage -> (input store, WIP, output store), warehouse names without the company suffix.
STAGE_WAREHOUSES: dict[str, tuple[str, str, str]] = {
	"Cotton Recycling": ("Cotton Waste Store", "Recycling WIP", "Recycled Fiber Store"),
	"Fiber Dyeing": ("Recycled Fiber Store", "Fiber Dyeing WIP", "Dyed Fiber Store"),
	"Spinning": ("Recycled Fiber Store", "Spinning WIP", "Yarn Store"),
	"Indigo Dyeing": ("Yarn Store", "Indigo WIP", "Beam Store"),
	"Weaving": ("Beam Store", "Weaving WIP", "Grey Fabric Store"),
	"Finishing": ("Grey Fabric Store", "Finishing WIP", "Finished Lot Store"),
	"Garments": ("Fabric A Store", "Cutting WIP", "Garment FG Store"),
	"Terry Weaving": ("HT Yarn Store", "Terry Weaving WIP", "Grey Terry Store"),
	"Flat Weaving": ("HT Yarn Store", "Flat Weaving WIP", "Grey Sheeting Store"),
	"Processing": ("Grey Terry Store", "Processing WIP", "Processed Terry Store"),
	"Printing": ("Grey Sheeting Store", "Printing WIP", "Processed Sheeting Store"),
	"Cut-to-Piece": ("Processed Terry Store", "CTP WIP", "Towel Pieces Store"),
	"Set Assembly": ("Towel Pieces Store", "Set Assembly WIP", "HT FG Store"),
}

CONSUMABLE_ITEM_GROUPS: tuple[str, ...] = ("Chemicals & Dyes", "Trims", "Packing Material")
WASTE_ITEM_GROUP = "Waste"

UTILITY_ABSORBED_PREFIX = "Utilities (absorbed)"

# Dye Recipe -> generated BOM operations: (operation, workstation, minutes per BOM qty), QI template.
DYE_PROCESS_ROUTES: dict[str, dict] = {
	"Fiber Dyeing": {
		"operations": [("Fiber Loading", "FD-01", 30), ("Fiber Dyeing", "FD-01", 240), ("Hydro & Drying", "FD-01", 90)],
		"qi_template": "QIT-DF",
	},
	"Indigo Dyeing": {
		"operations": [
			("Ball Warping", "WRP-01", 60),
			("Rope Indigo Dyeing", "IRR-01", 180),
			("Long Chain Beaming", "LCB-01", 60),
			("Sizing", "SZ-01", 90),
		],
		"qi_template": "QIT-IND",
	},
	"Processing": {
		"operations": [("Soft-flow Bleaching", "SFT-01", 300), ("Tumble Drying", "TMB-01", 180)],
		"qi_template": "QIT-TERRY-PROC",
	},
	"Printing": {
		"operations": [("Rotary Printing", "RTP-01", 40), ("Curing", "CUR-01", 50)],
		"qi_template": "QIT-SHEET-PRINT",
	},
	"Knit Dyeing": {
		"operations": [("Jet Dyeing", "JET-01", 480)],
		"qi_template": None,
	},
}

DEPARTMENT_ROLES: tuple[str, ...] = (
	"Recycling User",
	"Spinning User",
	"Dyeing User",
	"Indigo User",
	"Weaving User",
	"Finishing QA User",
	"Garment User",
	"Dye Lab Manager",
	"Production Director",
	"Plant Controller",
)
DIRECTOR_ROLES: tuple[str, ...] = ("CEO", "CFO", "Board Viewer")
ROLES: tuple[str, ...] = DEPARTMENT_ROLES + DIRECTOR_ROLES

SETTINGS_DEFAULTS: dict[str, float | int] = {
	"grade_a_max_points": 28,
	"grade_b_max_points": 40,
	"default_bundle_size": 20,
	"utility_absorption_enabled": 1,
}
