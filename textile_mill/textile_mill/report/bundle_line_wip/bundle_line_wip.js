frappe.query_reports["Bundle Line WIP"] = {
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
			fieldname: "cut_plan",
			label: __("Cut Plan"),
			fieldtype: "Link",
			options: "Cut Plan",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nCut\nIn Stitching\nStitched\nRejected",
		},
	],
};
