const BUNDLE_API = "textile_mill.textile_mill.doctype.bundle_ticket.bundle_ticket";

frappe.pages["bundle-scan"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Bundle Scan"), single_column: true });
	new BundleScan(page);
};

class BundleScan {
	constructor(page) {
		this.page = page;
		this.$body = $(`
			<div class="bundle-scan" style="max-width:720px;margin:24px auto;">
				<div class="form-group">
					<label class="control-label">${__("Scan or type bundle number, then Enter")}</label>
					<input type="text" class="form-control input-lg bundle-input" autocomplete="off" placeholder="BDL-26-000001">
				</div>
				<div class="line-field"></div>
				<div class="bundle-result" style="margin-top:16px;"></div>
			</div>`).appendTo(page.body);
		this.line = frappe.ui.form.make_control({
			parent: this.$body.find(".line-field"),
			df: { fieldtype: "Link", options: "Workstation", label: __("Stitch Line"), fieldname: "stitch_line",
				get_query: () => ({ filters: { workstation_type: "Sewing Line" } }) },
			render_input: true,
		});
		this.$input = this.$body.find(".bundle-input");
		this.$result = this.$body.find(".bundle-result");
		this.$input.on("keydown", (e) => {
			if (e.key === "Enter") this.load(this.$input.val());
		});
		setTimeout(() => this.$input.trigger("focus"), 300);
	}

	load(name) {
		if (!name) return;
		frappe.call({ method: `${BUNDLE_API}.get_bundle`, args: { name } }).then((r) => this.render(r.message));
	}

	act(status) {
		frappe.call({
			method: `${BUNDLE_API}.set_status`,
			args: { name: this.bundle.name, status, stitch_line: this.line.get_value() },
		}).then((r) => {
			frappe.show_alert({ message: __("Bundle {0}: {1}", [this.bundle.name, status]), indicator: "green" });
			this.render(r.message);
			this.$input.val("").trigger("focus");
		});
	}

	complete() {
		frappe.call({ method: `${BUNDLE_API}.complete_work_order`, args: { work_order: this.wo.name } }).then((r) => {
			frappe.msgprint(__("Manufacture entry {0} created.", [r.message]));
			this.load(this.bundle.name);
		});
	}

	render(data) {
		this.bundle = data.bundle;
		this.wo = data.work_order;
		const b = this.bundle, wo = this.wo;
		const color = { Cut: "orange", "In Stitching": "blue", Stitched: "green", Rejected: "red" }[b.status];
		this.$result.html(`
			<div class="frappe-card" style="padding:16px;">
				<div style="display:flex;justify-content:space-between;align-items:center;">
					<h4 style="margin:0;">${frappe.utils.escape_html(b.name)}</h4>
					<span class="indicator-pill ${color}">${__(b.status)}</span>
				</div>
				<div class="text-muted" style="margin:8px 0 16px;">
					${frappe.utils.escape_html(b.variant_item)} · ${__("Size")} ${frappe.utils.escape_html(b.size || "")} ·
					${__("Bundle")} ${b.bundle_no} · ${__("Qty")} ${b.qty}
				</div>
				<div class="actions" style="display:flex;gap:8px;flex-wrap:wrap;"></div>
				<hr>
				<div class="text-muted small">
					${__("Work Order")} <a href="/app/work-order/${encodeURIComponent(wo.name)}">${frappe.utils.escape_html(wo.name)}</a>:
					${wo.stitched_qty} / ${wo.qty} ${__("stitched")}, ${wo.pending_bundles} ${__("bundles pending")}, ${__("produced")} ${wo.produced_qty}
				</div>
			</div>`);
		const $a = this.$result.find(".actions");
		if (b.status === "Cut") $(`<button class="btn btn-primary">${__("Start Stitching")}</button>`).on("click", () => this.act("In Stitching")).appendTo($a);
		if (["Cut", "In Stitching"].includes(b.status)) {
			$(`<button class="btn btn-success">${__("Mark Stitched")}</button>`).on("click", () => this.act("Stitched")).appendTo($a);
			$(`<button class="btn btn-danger">${__("Reject")}</button>`).on("click", () => this.act("Rejected")).appendTo($a);
		}
		if (wo.can_complete) $(`<button class="btn btn-default">${__("Complete Work Order")}</button>`).on("click", () => this.complete()).appendTo($a);
	}
}
