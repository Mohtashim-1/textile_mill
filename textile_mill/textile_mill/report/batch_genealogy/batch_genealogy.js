frappe.query_reports["Batch Genealogy"] = {
	filters: [
		{
			fieldname: "batch_no",
			label: __("Batch"),
			fieldtype: "Link",
			options: "Batch",
		},
		{
			fieldname: "work_order",
			label: __("Work Order (garments)"),
			fieldtype: "Link",
			options: "Work Order",
		},
		{
			fieldname: "delivery_note",
			label: __("Delivery Note"),
			fieldtype: "Link",
			options: "Delivery Note",
		},
		{
			fieldname: "direction",
			label: __("Direction"),
			fieldtype: "Select",
			options: "Backward\nForward",
			default: "Backward",
		},
		{
			fieldname: "max_depth",
			label: __("Max Depth"),
			fieldtype: "Int",
			default: 10,
		},
	],
	tree: true,
	name_field: "name",
	parent_field: "parent_node",
	initial_depth: 4,
};
