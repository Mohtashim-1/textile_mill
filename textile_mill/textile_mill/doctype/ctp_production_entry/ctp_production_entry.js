frappe.ui.form.on("CTP Production Entry", {
	setup(frm) {
		frm.set_query("work_order", () => ({ filters: { docstatus: 1, dm_stage: "Cut-to-Piece", status: ["not in", ["Completed", "Closed", "Stopped"]] } }));
		frm.set_query("line", () => ({ filters: { dm_stage: "Cut-to-Piece" } }));
		frm.set_query("weight_check", () => ({ filters: { docstatus: 1, item_code: frm.doc.product_item } }));
		frm.set_query("batch_no", "source_batches", () => ({ filters: { item: frm.doc.source_item } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.product_item && !frm.doc.weight_check) {
			frm.add_custom_button(__("New Piece Weight Check"), () => {
				frappe.new_doc("Piece Weight Check", { item_code: frm.doc.product_item, work_order: frm.doc.work_order });
			});
		}
		for (const field of ["transfer_entry", "stock_entry"]) {
			if (frm.doc[field]) {
				frm.add_custom_button(__(frm.fields_dict[field].df.label), () => frappe.set_route("Form", "Stock Entry", frm.doc[field]), __("View"));
			}
		}
	},
});
