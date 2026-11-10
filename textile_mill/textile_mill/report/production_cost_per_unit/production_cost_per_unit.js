frappe.query_reports["Production Cost per Unit"] = {
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
			fieldname: "dm_stage",
			label: __("Stage"),
			fieldtype: "Select",
			options: "\nCotton Recycling\nFiber Dyeing\nSpinning\nIndigo Dyeing\nWeaving\nFinishing\nGarments\nTerry Weaving\nFlat Weaving\nProcessing\nPrinting\nCut-to-Piece\nSet Assembly\nPacking\nKnitting\nKnit Dyeing\nKnit Finishing\nKnit Garments",
		},
		{
			fieldname: "work_order",
			label: __("Work Order"),
			fieldtype: "Link",
			options: "Work Order",
		},
	],
};
