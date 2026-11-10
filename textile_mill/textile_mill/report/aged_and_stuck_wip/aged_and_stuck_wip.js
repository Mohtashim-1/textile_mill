frappe.query_reports["Aged and Stuck WIP"] = {
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
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "statuses",
			label: __("Inventory Statuses"),
			fieldtype: "Data",
			default: "WIP,QC Hold,B-Grade",
			description: __("Comma-separated"),
		},
		{
			fieldname: "min_age_days",
			label: __("Minimum Age (days)"),
			fieldtype: "Int",
			default: 0,
		},
	],
};
