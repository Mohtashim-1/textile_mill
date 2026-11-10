frappe.query_reports["Lot Recall Trace"] = {
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
			fieldname: "batch_no",
			label: __("Batch / Lot"),
			fieldtype: "Link",
			options: "Batch",
			reqd: 1,
		},
	],
};
