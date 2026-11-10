"""KPI Definitions, default KPI Targets and Downtime Reasons (Part C §5, §6.1). Idempotent."""

import frappe

from textile_mill.dashboards.kpi import CALCULATORS

HIGHER, LOWER = "Higher is better", "Lower is better"

# code: (name, unit, direction, description)
KPI_DEFINITIONS = {
	"REVENUE": ("Revenue", "PKR", HIGHER, "Sum of net totals of submitted Sales Invoices in the period."),
	"GROSS_MARGIN_PCT": ("Gross Margin %", "%", HIGHER, "(Revenue − COGS) ÷ Revenue; COGS = GL on Cost of Goods Sold accounts."),
	"PRODUCTION_VALUE": ("Production Value", "PKR", HIGHER, "Value of graded fabric rolls plus garments produced in the period."),
	"FINISHED_FABRIC_M": ("Finished Fabric", "m", HIGHER, "Meters produced by Finishing Manufacture entries."),
	"GARMENTS_PCS": ("Garments Produced", "pcs", HIGHER, "Pieces produced by Garments Manufacture entries."),
	"ORDER_BOOK": ("Order Book", "PKR", HIGHER, "Undelivered quantity × rate on open Sales Orders."),
	"OTD_PCT": ("On-Time Delivery %", "%", HIGHER, "Delivery Note lines posted on or before the Sales Order line delivery date ÷ all lines."),
	"BOOKED": ("Booked", "PKR", HIGHER, "Net total of Sales Orders dated in the period."),
	"DELIVERED": ("Delivered", "PKR", HIGHER, "Net total of Delivery Notes posted in the period."),
	"INVENTORY_VALUE": ("Inventory Value", "PKR", LOWER, "Stock value of all company warehouses (Bin)."),
	"WIP_VALUE": ("WIP Value", "PKR", LOWER, "Stock value in WIP warehouses."),
	"RECOVERY_YIELD": ("Recovery Yield", "%", HIGHER, "Recycled fiber output ÷ cotton waste input (Recycling Manufacture entries)."),
	"STAGE_YIELD": ("Stage Yield", "%", HIGHER, "Main output ÷ main input (chemicals and trims excluded); weaving shows m per kg."),
	"WASTE_PCT": ("Waste %", "%", LOWER, "Scrap quantity ÷ main input."),
	"PLAN_ATTAINMENT": ("Plan Attainment", "%", HIGHER, "Produced ÷ planned qty of Work Orders starting in the period."),
	"AVAILABILITY": ("Availability", "%", HIGHER, "Run time ÷ (run time + unplanned downtime)."),
	"PERFORMANCE": ("Performance", "%", HIGHER, "Actual output ÷ (run hours × rated output per hour)."),
	"QUALITY_RATE": ("Quality Rate", "%", HIGHER, "Good output ÷ total output (A-grade for fabric, QI-accepted elsewhere)."),
	"OEE": ("OEE", "%", HIGHER, "Availability × Performance × Quality."),
	"DOWNTIME_HRS": ("Unplanned Downtime", "hrs", LOWER, "Unplanned Machine Downtime Log minutes plus loom stops ÷ 60."),
	"OPEN_WO": ("Open Work Orders", "count", LOWER, "Work Orders Not Started or In Process (delayed = past planned end)."),
	"REDYE_PCT": ("Re-dye %", "%", LOWER, "Dyeing Work Orders with a corrective job card ÷ all dyeing Work Orders."),
	"WIP_AGING_DAYS": ("WIP Aging", "days", LOWER, "Value-weighted days since WIP batches were made."),
	"COST_PER_UNIT": ("Cost per Unit", "PKR/kg", LOWER, "Actual cost ÷ output in the stage's output unit (report 9.2)."),
	"STD_VARIANCE_PCT": ("Standard Cost Variance %", "%", LOWER, "(Actual − standard) ÷ standard cost per unit."),
	"STD_VARIANCE_AMOUNT": ("Standard Cost Variance", "PKR", LOWER, "Σ (actual − standard) × output over Work Orders."),
	"UTILITY_VARIANCE": ("Utility Variance", "PKR", HIGHER, "Absorbed − actual utility cost (negative = under-absorbed)."),
	"CHEM_VARIANCE_PCT": ("Chemical Variance %", "%", LOWER, "(Actual chemical kg − recipe kg) ÷ recipe kg."),
	"A_GRADE_PCT": ("A-Grade %", "%", HIGHER, "A meters ÷ inspected meters (Fabric Roll Inspection)."),
	"AVG_DEFECT_POINTS": ("Avg Defect Points", "count", LOWER, "Meter-weighted points per 100 sq yd."),
	"FIRST_PASS_QI": ("First-pass QI %", "%", HIGHER, "Manufacture entries whose first in-process QI was accepted."),
	"LOOM_EFF": ("Loom Efficiency", "%", HIGHER, "Meter-weighted efficiency from Loom Shift Production."),
	"CUTTING_VAR_PCT": ("Cutting Variance %", "%", LOWER, "Σ cutting variance m ÷ Σ standard fabric m (Cut Plans)."),
	"ACTIVE_ITEMS": ("Materials in Stock", "count", HIGHER, "Distinct items with positive stock."),
	"LOW_STOCK_COUNT": ("Low Stock Items", "count", LOWER, "Item-warehouse pairs below their reorder level."),
	"AGED_STOCK_VALUE": ("Aged Stock (>90 d)", "PKR", LOWER, "Value of usable batches made more than 90 days ago."),
	"INVENTORY_ACCURACY": ("Inventory Accuracy", "%", HIGHER, "1 − Σ|counted − system| ÷ Σ counted in Stock Reconciliations."),
	"AR_OVERDUE": ("AR Overdue", "PKR", LOWER, "Outstanding on Sales Invoices past due date."),
	"AP_DUE_30": ("AP Due (30 d)", "PKR", LOWER, "Outstanding on Purchase Invoices due within 30 days."),
	"CASH_POSITION": ("Cash Position", "PKR", HIGHER, "Balance of Bank and Cash accounts."),
	"PURCHASES": ("Purchases", "PKR", HIGHER, "Net total of Purchase Receipts in the period."),
	"OPEN_PO_VALUE": ("Open PO Value", "PKR", LOWER, "Unreceived quantity × rate on open Purchase Orders."),
	"OVERDUE_PO_LINES": ("PO Lines Overdue", "count", LOWER, "Open PO lines past their schedule date."),
	"COTTON_WASTE_PRICE": ("Cotton Waste Price", "PKR/kg", LOWER, "Average received price per kg of cotton waste."),
	"VIRGIN_COTTON_PRICE": ("Virgin Cotton Price", "PKR/kg", LOWER, "Average received price per kg of virgin cotton."),
	"SUPPLIER_QI_REJECTION": ("Supplier QI Rejection %", "%", LOWER, "Rejected incoming QIs ÷ all incoming QIs."),
	"ORDERS_AT_RISK": ("Orders at Risk", "count", LOWER, "Open SO lines where stock + WIP is short of the pending quantity."),
	"PRICE_REALISATION_FABRIC": ("Fabric Price Realisation", "PKR/m", HIGHER, "Average invoiced price per meter of finished fabric."),
	"CTP_YIELD": ("CTP Yield", "%", HIGHER, "A-grade pieces ÷ pieces planned from the fabric issued (CTP Production Entries)."),
	"SECONDS_PCT": ("Seconds %", "%", LOWER, "Seconds ÷ pieces cut (CTP Production Entries)."),
	"WEIGHT_VARIANCE_PCT": ("Piece Weight Variance %", "%", LOWER,
		"Piece-weighted (avg − target) ÷ target from Piece Weight Checks; + = cotton give-away. RAG on the absolute value."),
	"COTTON_GIVEAWAY_KG": ("Cotton Give-away", "kg", LOWER, "Σ (avg − target weight) × pieces released by each weight check."),
	"SET_COMPLETION_PCT": ("Set Completion %", "%", HIGHER, "(Sets on hand + buildable from components) ÷ open SO set qty."),
	"CARTONS_SHIPPED": ("Cartons Shipped", "count", HIGHER, "Cartons on packing lists whose Delivery Note posted in the period."),
	"TERRY_LOOM_EFF": ("Terry Loom Efficiency", "%", HIGHER, "Kg-weighted efficiency of terry Loom Shift Production."),
	"KNIT_EFF": ("Knitting Efficiency", "%", HIGHER, "Kg-weighted machine efficiency from Knitting Shift Production."),
	"KNIT_DEFECTS_PER_ROLL": ("Knit Defects per Roll", "count", LOWER, "Holes / needle-line defects ÷ greige rolls knitted."),
	"DYE_MACHINE_LOAD_PCT": ("Dye Machine Load %", "%", HIGHER, "Knit dyeing Work Order qty ÷ jet batch capacity (average per batch)."),
	"KNIT_DYE_LOSS_PCT": ("Knit Dyeing Loss %", "%", LOWER, "100 − Knit Dyeing stage yield (dyed kg ÷ greige kg)."),
	"SHRINKAGE_SPIRALITY_PASS_PCT": ("Shrinkage & Spirality Pass %", "%", HIGHER,
		"Accepted shrinkage and spirality readings ÷ all such readings on finished knit QIs."),
}

# (kpi, stage, target, amber, red)
KPI_TARGETS = [
	("RECOVERY_YIELD", None, 85, 82, 80),
	("STAGE_YIELD", "Cotton Recycling", 85, 82, 80),
	("STAGE_YIELD", "Fiber Dyeing", 97, 95, 93),
	("STAGE_YIELD", "Spinning", 88, 86, 84),
	("STAGE_YIELD", "Indigo Dyeing", 98.5, 97.5, 96),
	("STAGE_YIELD", "Finishing", 95, 94, 92),
	("OEE", None, 75, 65, 55),
	("LOOM_EFF", None, 85, 80, 75),
	("REDYE_PCT", None, 3, 5, 8),
	("A_GRADE_PCT", None, 93, 90, 85),
	("CUTTING_VAR_PCT", None, 3, 4, 6),
	("CHEM_VARIANCE_PCT", None, 3, 6, 10),
	("OTD_PCT", None, 95, 90, 85),
	("GROSS_MARGIN_PCT", None, 18, 14, 10),
	("INVENTORY_ACCURACY", None, 99, 98, 96),
	("FIRST_PASS_QI", None, 95, 90, 85),
	("PLAN_ATTAINMENT", None, 95, 90, 80),
	("STD_VARIANCE_PCT", None, 2, 5, 10),
	("SUPPLIER_QI_REJECTION", None, 2, 5, 10),
	("STAGE_YIELD", "Terry Weaving", 98, 97, 95),
	("STAGE_YIELD", "Processing", 94, 93, 91),
	("STAGE_YIELD", "Printing", 97, 96, 94),
	("CTP_YIELD", None, 97, 96, 94),
	("SECONDS_PCT", None, 2, 3, 5),
	("WEIGHT_VARIANCE_PCT", None, 1, 1, 3),
	("SET_COMPLETION_PCT", None, 100, 95, 90),
	("TERRY_LOOM_EFF", None, 85, 80, 75),
	("KNIT_EFF", None, 85, 80, 75),
	("KNIT_DEFECTS_PER_ROLL", None, 0.5, 1, 2),
	("DYE_MACHINE_LOAD_PCT", None, 90, 80, 70),
	("KNIT_DYE_LOSS_PCT", None, 5, 6, 8),
	("SHRINKAGE_SPIRALITY_PASS_PCT", None, 98, 95, 90),
	("STAGE_YIELD", "Knit Dyeing", 95, 94, 92),
	("STAGE_YIELD", "Knit Finishing", 98, 97, 95),
]

DOWNTIME_REASONS = [
	("MECH-BRK", "Mechanical breakdown", "Mechanical", 0),
	("ELEC", "Electrical fault", "Electrical", 0),
	("YARN-SHT", "Yarn shortage", "Material Shortage", 0),
	("BEAM-CHG", "Beam change", "Changeover", 0),
	("PM", "Planned maintenance", "Planned Maintenance", 1),
	("PWR", "Power failure", "Power Failure", 0),
	("SHADE-HOLD", "Shade hold", "Quality", 0),
	("NO-ORD", "No order", "No Order", 1),
	("LOOM-STOP", "Loom stops (shift log)", "Operator", 0),
]


def seed_kpis() -> None:
	for code, (name, unit, direction, description) in KPI_DEFINITIONS.items():
		values = {
			"kpi_name": name,
			"unit": unit,
			"direction": direction,
			"calculator": f"textile_mill.dashboards.kpi.{CALCULATORS[code].__name__}",
			"description": description,
		}
		if frappe.db.exists("KPI Definition", code):
			frappe.db.set_value("KPI Definition", code, values)
		else:
			frappe.get_doc({"doctype": "KPI Definition", "kpi_code": code, **values}).insert(ignore_permissions=True)

	for kpi, stage, target, amber, red in KPI_TARGETS:
		filters = {"kpi": kpi, "stage": stage or "", "plant": ["is", "not set"]}
		if not frappe.db.exists("KPI Target", filters):
			frappe.get_doc(
				{"doctype": "KPI Target", "kpi": kpi, "stage": stage, "target_value": target, "amber_threshold": amber,
				"red_threshold": red, "effective_from": "2026-01-01"}
			).insert(ignore_permissions=True)

	for code, name, category, planned in DOWNTIME_REASONS:
		if not frappe.db.exists("Downtime Reason", code):
			frappe.get_doc(
				{"doctype": "Downtime Reason", "reason_code": code, "reason_name": name, "category": category, "is_planned": planned}
			).insert(ignore_permissions=True)
