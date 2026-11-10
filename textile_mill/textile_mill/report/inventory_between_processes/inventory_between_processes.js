frappe.query_reports["Inventory Between Processes"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "group_by_warehouse_group",
			label: __("Summarise by Warehouse Group"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
