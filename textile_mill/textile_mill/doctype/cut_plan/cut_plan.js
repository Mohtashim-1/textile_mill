frappe.ui.form.on("Cut Plan", {
	setup(frm) {
		frm.set_query("style_template", () => ({ filters: { has_variants: 1 } }));
		frm.set_query("batch_no", "fabric_rolls", () => ({ filters: { item: frm.doc.fabric_item } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Allocate Rolls"), () => {
				frm.call("allocate_rolls").then(() => frm.reload_doc());
			});
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Complete Stitched Work Orders"), () => {
				frm.call("complete_stitched_work_orders").then((r) => {
					const done = r.message || [];
					frappe.msgprint(done.length ? __("Completed: {0}", [done.join(", ")]) : __("No Work Order is fully stitched yet."));
					frm.reload_doc();
				});
			});
			frm.add_custom_button(__("Bundle Tickets"), () => frappe.set_route("List", "Bundle Ticket", { cut_plan: frm.doc.name }));
			frm.add_custom_button(__("Bundle Scan"), () => frappe.set_route("bundle-scan"));
		}
	},
});
