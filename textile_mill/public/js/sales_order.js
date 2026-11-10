frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		frm.add_custom_button(__("Order Cost & Profit"), () => {
			frappe.set_route("query-report", "Order Cost & Profitability", { sales_order: frm.doc.name });
		}, __("View"));
	},
});
