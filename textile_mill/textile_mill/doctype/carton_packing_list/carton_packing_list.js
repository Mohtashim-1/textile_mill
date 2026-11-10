function print_packing(frm, format) {
	frappe.utils.print(frm.doctype, frm.doc.name, format, frm.doc.letter_head, frm.doc.language);
}

frappe.ui.form.on("Carton Packing List", {
	setup(frm) {
		frm.set_query("sales_order", () => ({ filters: { docstatus: 1, status: ["not in", ["Completed", "Closed"]] } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Generate Cartons"), () => {
				frm.call("generate_cartons").then(() => frm.reload_doc());
			});
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Carton Labels"), () => print_packing(frm, "Carton Label"), __("Print"));
			frm.add_custom_button(__("Packing List"), () => print_packing(frm, "Packing List"), __("Print"));
			if (!frm.doc.delivery_note) {
				frm.add_custom_button(__("Create Delivery Note"), () => {
					frm.call("create_delivery_note").then((r) => r.message && frappe.set_route("Form", "Delivery Note", r.message));
				});
			} else {
				frm.add_custom_button(__("Delivery Note"), () => frappe.set_route("Form", "Delivery Note", frm.doc.delivery_note));
			}
		}
	},
});
