frappe.query_reports["Set Completion"] = {
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
			fieldname: "item_code",
			label: __("Set Item"),
			fieldtype: "Link",
			options: "Item",
			get_query: () => ({ filters: { dm_stage: "Set Assembly" } }),
		},
	],
};
