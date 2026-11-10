frappe.ui.form.on("Work Order", {
	setup(frm) {
		frm.set_query("dye_recipe", () => ({
			filters: { docstatus: 1, workflow_state: "Production Approved", is_obsolete: 0 },
		}));
	},
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		if (frm.doc.dm_stage === "Indigo Dyeing") {
			frm.add_custom_button(__("Indigo Range Log"), () => {
				frappe.new_doc("Indigo Range Log", { work_order: frm.doc.name });
			}, __("Create"));
		}
		if (frm.doc.dm_stage === "Weaving" || frm.doc.dm_stage === "Terry Weaving" || frm.doc.dm_stage === "Flat Weaving") {
			frm.add_custom_button(__("Loom Shift Production"), () => {
				frappe.new_doc("Loom Shift Production", { work_order: frm.doc.name });
			}, __("Create"));
		}
		if (frm.doc.dm_stage === "Knitting") {
			frm.add_custom_button(__("Knitting Shift Production"), () => {
				frappe.new_doc("Knitting Shift Production", { work_order: frm.doc.name });
			}, __("Create"));
		}
		if (frm.doc.dm_stage === "Cut-to-Piece") {
			frm.add_custom_button(__("CTP Production Entry"), () => {
				frappe.new_doc("CTP Production Entry", { work_order: frm.doc.name });
			}, __("Create"));
		}
	},
});
