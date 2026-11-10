frappe.ui.form.on("Dye Recipe", {
	setup(frm) {
		frm.set_query("shade", () => ({ filters: { process_type: frm.doc.process_type } }));
		frm.set_query("item_code", "chemicals", () => ({ filters: { item_group: "Chemicals & Dyes" } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.workflow_state === "Production Approved" && !frm.doc.bom) {
			frm.add_custom_button(__("Create BOM"), () => {
				frm.call({ method: "textile_mill.textile_mill.doctype.dye_recipe.dye_recipe.create_bom", args: { recipe: frm.doc.name } })
					.then((r) => {
						frappe.show_alert({ message: __("BOM {0} created", [r.message]), indicator: "green" });
						frm.reload_doc();
					});
			});
		}
		if (frm.doc.bom) {
			frm.add_custom_button(__("Open BOM"), () => frappe.set_route("Form", "BOM", frm.doc.bom));
		}
	},
});
