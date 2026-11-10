frappe.ui.form.on("Fabric Roll Inspection", {
	setup(frm) {
		frm.set_query("lot_batch", () => ({ filters: { item: frm.doc.lot_item } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.stock_entry) {
			frm.add_custom_button(__("Roll Batches"), () =>
				frappe.set_route("List", "Batch", { dm_source_doc: frm.doc.name })
			);
		}
	},
});
