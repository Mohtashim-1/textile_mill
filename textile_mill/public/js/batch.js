frappe.ui.form.on("Batch", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Show Genealogy"), () => {
			frappe.set_route("query-report", "Batch Genealogy", { batch_no: frm.doc.name, direction: "Backward" });
		});
	},
});
