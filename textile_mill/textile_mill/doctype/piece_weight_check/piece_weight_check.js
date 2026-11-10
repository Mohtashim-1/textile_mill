frappe.ui.form.on("Piece Weight Check", {
	setup(frm) {
		frm.set_query("item_code", () => ({ filters: { dm_target_weight_kg: [">", 0] } }));
		frm.set_query("work_order", () => ({ filters: { docstatus: 1, production_item: frm.doc.item_code } }));
	},
	refresh(frm) {
		const colors = { Pass: "green", Overweight: "orange", Underweight: "red" };
		if (frm.doc.result) {
			frm.dashboard.set_headline_alert(
				`<span class="indicator ${colors[frm.doc.result]}">${__(frm.doc.result)}: ${format_number(frm.doc.variance_pct, null, 2)}% ${__("vs target")}</span>`
			);
		}
	},
});

frappe.ui.form.on("Weight Sample", {
	samples_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "sample_no", frm.doc.samples.length);
	},
});
