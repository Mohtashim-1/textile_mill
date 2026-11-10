frappe.query_reports["Loom Efficiency"] = {
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
		{
			fieldname: "loom",
			label: __("Loom"),
			fieldtype: "Link",
			options: "Workstation",
		},
		{
			fieldname: "weaver",
			label: __("Weaver"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: "\nLoom\nWeaver\nShift",
		},
	],
};
