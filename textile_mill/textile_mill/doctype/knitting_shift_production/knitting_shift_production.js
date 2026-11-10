// Copyright (c) 2026, Mission20 Zero and contributors
// For license information, please see license.txt

frappe.ui.form.on("Knitting Shift Production", {
	setup(frm) {
		frm.set_query("work_order", () => ({ filters: { docstatus: 1, dm_stage: "Knitting", status: ["not in", ["Completed", "Closed", "Stopped"]] } }));
		frm.set_query("machine", "machines", () => ({ filters: { dm_stage: "Knitting" } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.stock_entry) {
			frm.add_custom_button(__("Stock Entry"), () => frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry), __("View"));
		}
		if (frm.doc.greige_batch) {
			frm.add_custom_button(__("Greige Batch"), () => frappe.set_route("Form", "Batch", frm.doc.greige_batch), __("View"));
		}
	},
});
