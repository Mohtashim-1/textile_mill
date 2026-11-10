frappe.query_reports["Order Book by Business Line"] = {
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
			fieldname: "business_line",
			label: __("Business Line"),
			fieldtype: "Select",
			options: "\nDenim\nHome Textile\nKnitting",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "as_on_date",
			label: __("As On"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};
