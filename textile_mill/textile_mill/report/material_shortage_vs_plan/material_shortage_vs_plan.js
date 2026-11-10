frappe.query_reports["Material Shortage vs Plan"] = {
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
			fieldname: "only_exceptions",
			label: __("Exceptions only"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
