frappe.query_reports["Order Cost and Profitability"] = {
	filters: [
		{
			fieldname: "sales_order",
			label: __("Sales Order"),
			fieldtype: "Link",
			options: "Sales Order",
			reqd: 1,
		},
	],
};
