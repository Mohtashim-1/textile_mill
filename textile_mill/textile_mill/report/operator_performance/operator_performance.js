frappe.query_reports["Operator Performance"] = {
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
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
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
			fieldname: "machine_type",
			label: __("Machines"),
			fieldtype: "Select",
			options: "\nLoom\nKnitting",
		},
		{
			fieldname: "loom_type",
			label: __("Loom Type"),
			fieldtype: "Select",
			options: "\nAir-jet Denim\nTerry\nFlat Wide",
		},
		{
			fieldname: "shift",
			label: __("Shift"),
			fieldtype: "Link",
			options: "Mill Shift",
		},
	],
};
