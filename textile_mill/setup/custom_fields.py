"""Custom fields on standard DocTypes (Part B §7, Part C §5.6–5.7, Part D §D2, Part E §E2).

Kept as code (applied on install/migrate) instead of exported fixture JSON so the stage
options stay in one place (`textile_mill.constants`).
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from textile_mill.constants import INVENTORY_STATUSES, ITEM_STAGES, PRODUCTION_STAGES

MODULE = "Textile Mill"
ITEM_STAGE_OPTIONS = "\n" + "\n".join(ITEM_STAGES)
STAGE_OPTIONS = "\n" + "\n".join(PRODUCTION_STAGES)


def _f(fieldname: str, fieldtype: str, label: str, insert_after: str, **kw) -> dict:
	return {
		"fieldname": fieldname,
		"fieldtype": fieldtype,
		"label": label,
		"insert_after": insert_after,
		"module": MODULE,
		**kw,
	}


def get_custom_fields() -> dict[str, list[dict]]:
	return {
		"Item": [
			_f("dm_textile_section", "Section Break", "Textile", "description", collapsible=1),
			_f("dm_stage", "Select", "Stage", "dm_textile_section", options=ITEM_STAGE_OPTIONS,
				in_standard_filter=1),
			_f("dm_yarn_count_ne", "Float", "Yarn Count (Ne)", "dm_stage"),
			_f("dm_blend_composition", "Data", "Blend Composition", "dm_yarn_count_ne"),
			_f("dm_shade", "Link", "Shade", "dm_blend_composition", options="Shade"),
			_f("dm_design", "Data", "Design", "dm_shade"),
			_f("dm_textile_cb1", "Column Break", "", "dm_design"),
			_f("dm_fabric_construction", "Data", "Fabric Construction", "dm_textile_cb1"),
			_f("dm_width_inch", "Float", "Width (inch)", "dm_fabric_construction"),
			_f("dm_weight_oz", "Float", "Weight (oz/sq yd)", "dm_width_inch"),
			_f("dm_target_gsm", "Float", "Target GSM", "dm_weight_oz"),
			_f("dm_textile_cb2", "Column Break", "", "dm_target_gsm"),
			_f("dm_target_weight_kg", "Float", "Target Weight per Piece (kg)", "dm_textile_cb2"),
			_f("dm_weight_tolerance_pct", "Float", "Weight Tolerance %", "dm_target_weight_kg", default="5"),
			_f("dm_pieces_per_kg", "Float", "Pieces per kg", "dm_weight_tolerance_pct", read_only=1),
			_f("dm_size_cm", "Data", "Size (cm)", "dm_pieces_per_kg", description="e.g. 70x140"),
			_f("dm_machine_dia", "Float", "Machine Dia (inch)", "dm_size_cm"),
			_f("dm_gauge", "Int", "Gauge", "dm_machine_dia"),
			_f("dm_stitch_length_mm", "Float", "Stitch Length (mm)", "dm_gauge"),
			_f("dm_label_specs_section", "Section Break", "Customer Label Specs", "dm_stitch_length_mm",
				collapsible=1),
			_f("dm_label_specs", "Table", "Customer Label Specs", "dm_label_specs_section",
				options="Customer Label Spec"),
		],
		"Batch": [
			_f("dm_textile_section", "Section Break", "Textile", "description", collapsible=1),
			_f("dm_stage", "Select", "Stage", "dm_textile_section", options=ITEM_STAGE_OPTIONS,
				in_standard_filter=1),
			_f("dm_grade", "Select", "Grade", "dm_stage", options="\nA\nB\nRejected", in_standard_filter=1),
			_f("dm_shade_group", "Data", "Shade Group", "dm_grade"),
			_f("dm_source_doctype", "Link", "Source DocType", "dm_shade_group", options="DocType", read_only=1),
			_f("dm_source_doc", "Dynamic Link", "Source Document", "dm_source_doctype",
				options="dm_source_doctype", read_only=1),
			_f("dm_textile_cb1", "Column Break", "", "dm_source_doc"),
			_f("dm_roll_length_m", "Float", "Roll Length (m)", "dm_textile_cb1"),
			_f("dm_roll_weight_kg", "Float", "Roll Weight (kg)", "dm_roll_length_m"),
			_f("dm_width_inch", "Float", "Width (inch)", "dm_roll_weight_kg"),
			_f("dm_gsm", "Float", "GSM", "dm_width_inch"),
			_f("dm_textile_cb2", "Column Break", "", "dm_gsm"),
			_f("dm_beam_nos", "Small Text", "Beam Nos", "dm_textile_cb2"),
			_f("dm_loom_list", "Small Text", "Loom List", "dm_beam_nos"),
			_f("dm_roll_list", "Small Text", "Roll List", "dm_loom_list"),
		],
		"Work Order": [
			_f("dm_stage", "Select", "Stage", "production_item", options=STAGE_OPTIONS, read_only=1,
				in_standard_filter=1, search_index=1),
			_f("dye_recipe", "Link", "Dye Recipe", "bom_no", options="Dye Recipe"),
			_f("cut_plan", "Link", "Cut Plan", "dye_recipe", options="Cut Plan", read_only=1, no_copy=1),
			_f("machine_load_pct", "Percent", "Machine Load %", "cut_plan", read_only=1,
				depends_on="eval:doc.dm_stage=='Knit Dyeing'"),
		],
		"Stock Entry": [
			_f("dm_textile_section", "Section Break", "Textile", "bom_info_section", collapsible=1),
			_f("dm_stage", "Select", "Stage", "dm_textile_section", options=STAGE_OPTIONS, read_only=1,
				in_standard_filter=1, search_index=1),
			_f("loom_shift_production", "Link", "Loom Shift Production", "dm_stage",
				options="Loom Shift Production", read_only=1, no_copy=1),
			_f("fabric_roll_inspection", "Link", "Fabric Roll Inspection", "loom_shift_production",
				options="Fabric Roll Inspection", read_only=1, no_copy=1),
			_f("dm_textile_cb1", "Column Break", "", "fabric_roll_inspection"),
			_f("cut_plan", "Link", "Cut Plan", "dm_textile_cb1", options="Cut Plan", read_only=1, no_copy=1),
			_f("ctp_production_entry", "Link", "CTP Production Entry", "cut_plan",
				options="CTP Production Entry", read_only=1, no_copy=1),
			_f("knitting_shift_production", "Link", "Knitting Shift Production", "ctp_production_entry",
				options="Knitting Shift Production", read_only=1, no_copy=1),
		],
		"Delivery Note": [
			_f("dm_carton_packing_list", "Link", "Carton Packing List", "po_no", options="Carton Packing List",
				read_only=1, no_copy=1),
		],
		"BOM": [
			_f("dye_recipe", "Link", "Dye Recipe", "item", options="Dye Recipe", read_only=1),
		],
		"Workstation": [
			_f("dm_textile_section", "Section Break", "Textile Capacity", "description", collapsible=1),
			_f("dm_stage", "Select", "Stage", "dm_textile_section", options=STAGE_OPTIONS, in_standard_filter=1),
			_f("dm_rated_output_per_hour", "Float", "Rated Output per Hour", "dm_stage"),
			_f("dm_textile_cb1", "Column Break", "", "dm_rated_output_per_hour"),
			_f("dm_output_uom", "Link", "Output UOM", "dm_textile_cb1", options="UOM"),
			_f("dm_planned_hours_per_day", "Float", "Planned Hours per Day", "dm_output_uom", default="24"),
		],
		"Warehouse": [
			_f("dm_inventory_status", "Select", "Inventory Status", "warehouse_name",
				options="\n" + "\n".join(INVENTORY_STATUSES), in_standard_filter=1),
		],
	}


def setup_custom_fields() -> None:
	create_custom_fields(get_custom_fields(), ignore_validate=False, update=True)
