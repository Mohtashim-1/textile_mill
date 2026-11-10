import { WidgetRenderer } from "./widgets";

const STORE_KEY = "dm_dash_filters";
const URL_KEYS = ["period", "from_date", "to_date", "compare_to", "company", "plant", "business_line"];

export class DMDashboard {
	constructor(wrapper, dashboard) {
		this.wrapper = $(wrapper);
		this.dashboard = dashboard;
		this.page_name = wrapper.id || frappe.get_route()[0];
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Dashboard"), single_column: true });
		this.renderer = new WidgetRenderer(this);
		this.auto_refresh = localStorage.getItem(`${STORE_KEY}:auto`) !== "0";
		this.$root = $(`<div class="dm-dash">
			<button class="btn btn-xs btn-default dm-tv-exit">${__("Exit TV mode")}</button>
			<div class="dm-filterbar"></div>
			<div class="dm-status"></div>
			<div class="dm-tiles"></div>
			<div class="dm-grid"></div>
		</div>`).appendTo(this.page.main);
		this.setup_actions();
		this.$root.find(".dm-tv-exit").on("click", () => this.toggle_tv());
		this.boot();
		$(window).on(`resize.${this.page_name}`, frappe.utils.debounce(() => this.renderer.resize(), 150));
		$(document).on(`fullscreenchange.${this.page_name}`, () => {
			if (!document.fullscreenElement) $("body").removeClass("dm-tv");
			setTimeout(() => this.renderer.resize(), 200);
		});
	}

	async boot() {
		const r = await frappe.call({ method: "textile_mill.dashboards.api.get_filter_options", args: { dashboard: this.dashboard } });
		this.options = r.message;
		this.filters = this.initial_filters();
		this.make_filter_bar();
		this.load();
	}

	stage_slug() {
		const slug = frappe.get_route()[1];
		return slug || this.filters?.stage_slug || "recycling";
	}

	initial_filters() {
		const saved = JSON.parse(localStorage.getItem(`${STORE_KEY}:${this.dashboard}`) || "{}");
		const query = frappe.utils.get_query_params();
		const f = {
			period: this.options.default_period,
			compare_to: this.options.default_compare,
			company: this.options.default_company,
			...saved,
		};
		URL_KEYS.forEach((k) => {
			if (query[k]) f[k] = query[k];
		});
		if (this.dashboard === "stage") f.stage_slug = this.stage_slug();
		return f;
	}

	persist() {
		const { stage_slug, ...rest } = this.filters;
		localStorage.setItem(`${STORE_KEY}:${this.dashboard}`, JSON.stringify(rest));
		const params = new URLSearchParams();
		URL_KEYS.forEach((k) => {
			if (this.filters[k] && (k !== "from_date" && k !== "to_date" || this.filters.period === "Custom")) params.set(k, this.filters[k]);
		});
		const query = params.toString();
		window.history.replaceState(window.history.state, "", window.location.pathname + (query ? `?${query}` : ""));
	}

	setup_actions() {
		this.page.set_secondary_action(__("Refresh"), () => this.load(true), "refresh");
		this.page.add_menu_item(__("TV mode"), () => this.toggle_tv());
		this.page.add_menu_item(__("Toggle auto-refresh"), () => {
			this.auto_refresh = !this.auto_refresh;
			localStorage.setItem(`${STORE_KEY}:auto`, this.auto_refresh ? "1" : "0");
			frappe.show_alert(this.auto_refresh ? __("Auto-refresh on") : __("Auto-refresh off"));
			this.schedule();
		});
		if (frappe.user.has_role(["System Manager", "Plant Controller"])) {
			this.page.add_menu_item(__("Rebuild KPI snapshots"), () => this.rebuild_snapshots());
		}
	}

	select(fieldname, label, options, value, onchange) {
		const $s = $(`<label class="dm-filter"><span>${__(label)}</span><select class="form-control input-xs" data-field="${fieldname}"></select></label>`);
		const $sel = $s.find("select");
		options.forEach((o) => {
			const opt = typeof o === "string" ? { value: o, label: __(o) } : o;
			$sel.append(`<option value="${frappe.utils.escape_html(opt.value)}">${frappe.utils.escape_html(opt.label)}</option>`);
		});
		$sel.val(value ?? "");
		$sel.on("change", () => onchange($sel.val()));
		return $s;
	}

	make_filter_bar() {
		const $bar = this.$root.find(".dm-filterbar").empty();
		const dashboards = this.options.dashboards.map((d) => ({ value: d.name, label: __(d.title) }));
		$bar.append(
			this.select("dashboard", "Dashboard", dashboards, this.dashboard, (v) =>
				frappe.set_route(v === "stage" ? ["dm-stage", this.filters.stage_slug || "recycling"] : [`dm-${v}`])
			)
		);
		if (this.dashboard === "stage") {
			const stages = this.options.stages.map((s) => ({ value: s.slug, label: __(s.title) }));
			$bar.append(this.select("stage_slug", "Stage", stages, this.filters.stage_slug, (v) => frappe.set_route("dm-stage", v)));
		}
		$bar.append(this.select("period", "Period", this.options.periods, this.filters.period, (v) => this.set({ period: v })));
		const $custom = $(`<span class="dm-custom-range">
			<label class="dm-filter"><span>${__("From")}</span><input type="date" class="form-control input-xs" data-field="from_date"></label>
			<label class="dm-filter"><span>${__("To")}</span><input type="date" class="form-control input-xs" data-field="to_date"></label>
		</span>`).appendTo($bar);
		$custom.find("[data-field=from_date]").val(this.filters.from_date || "");
		$custom.find("[data-field=to_date]").val(this.filters.to_date || "");
		$custom.on("change", "input", (e) => this.set({ [$(e.target).data("field")]: $(e.target).val() }));
		$custom.toggle(this.filters.period === "Custom");
		$bar.append(this.select("compare_to", "Compare to", this.options.compare_to, this.filters.compare_to, (v) => this.set({ compare_to: v })));
		if (this.options.companies.length > 1) {
			$bar.append(this.select("company", "Company", this.options.companies, this.filters.company, (v) => this.set({ company: v })));
		}
		$bar.append(this.select("plant", "Plant", [{ value: "", label: __("All plants") }, ...this.options.plants], this.filters.plant || "", (v) => this.set({ plant: v })));
		if ((this.options.line_dashboards || []).includes(this.dashboard)) {
			$bar.append(
				this.select("business_line", "Business line", this.options.business_lines, this.filters.business_line || this.options.default_line, (v) =>
					this.set({ business_line: v })
				)
			);
		}
	}

	set(changes) {
		Object.assign(this.filters, changes);
		this.$root.find(".dm-custom-range").toggle(this.filters.period === "Custom");
		if (this.filters.period === "Custom" && !(this.filters.from_date && this.filters.to_date)) return;
		this.load();
	}

	async load(refresh = false) {
		if (this.loading) return;
		this.loading = true;
		this.persist();
		this.$root.addClass("dm-loading");
		try {
			const r = await frappe.call({
				method: "textile_mill.dashboards.api.get_dashboard",
				args: { dashboard: this.dashboard, filters: { ...this.filters, refresh: refresh ? 1 : 0 } },
			});
			this.render(r.message);
		} finally {
			this.loading = false;
			this.$root.removeClass("dm-loading");
			this.schedule();
		}
	}

	render(data) {
		this.meta = data.meta;
		this.page.set_title(__(data.meta.title));
		document.title = `${__(data.meta.title)} | ${frappe.boot.sysdefaults.company || "ERP"}`;
		this.renderer.dispose();
		const m = data.meta;
		this.$root.find(".dm-status").html(`
			<span>${frappe.datetime.str_to_user(m.from_date)} – ${frappe.datetime.str_to_user(m.to_date)}</span>
			${m.compare_from ? `<span class="dm-muted">${__("vs")} ${frappe.datetime.str_to_user(m.compare_from)} – ${frappe.datetime.str_to_user(m.compare_until)}</span>` : ""}
			${m.sample_history ? `<span class="dm-badge dm-sample" title="${__("Trend lines before go-live use generated sample history")}">${__("Sample history")}</span>` : ""}
			<span class="dm-muted dm-updated">${__("Updated")} ${frappe.datetime.comment_when(m.generated_at)}${m.cached ? " · " + __("cached") : ""}${this.auto_refresh ? " · " + __("auto-refresh {0} min", [Math.round(m.refresh_seconds / 60)]) : ""}</span>`);
		const $tiles = this.$root.find(".dm-tiles").empty();
		data.tiles.forEach((t) => $tiles.append(this.renderer.tile(t)));
		const $grid = this.$root.find(".dm-grid").empty();
		data.widgets.forEach((w) => $grid.append(this.renderer.card(w)));
		setTimeout(() => this.renderer.resize(), 120);
	}

	schedule() {
		clearTimeout(this.timer);
		if (!this.auto_refresh || !this.meta) return;
		this.timer = setTimeout(() => {
			if (frappe.get_route()[0] === this.page_name && !document.hidden) this.load(true);
			else this.schedule();
		}, (this.meta.refresh_seconds || 300) * 1000);
	}

	toggle_tv() {
		const on = !$("body").hasClass("dm-tv");
		$("body").toggleClass("dm-tv", on);
		if (on && document.documentElement.requestFullscreen) document.documentElement.requestFullscreen().catch(() => {});
		if (!on && document.fullscreenElement) document.exitFullscreen();
		setTimeout(() => this.renderer.resize(), 300);
	}

	rebuild_snapshots() {
		frappe.prompt(
			[
				{ fieldname: "from_date", fieldtype: "Date", label: __("From"), reqd: 1, default: frappe.datetime.add_days(frappe.datetime.get_today(), -30) },
				{ fieldname: "to_date", fieldtype: "Date", label: __("To"), reqd: 1, default: frappe.datetime.get_today() },
			],
			(v) =>
				frappe
					.call({ method: "textile_mill.dashboards.snapshot.rebuild", args: v, freeze: true, freeze_message: __("Rebuilding snapshots…") })
					.then((r) => {
						frappe.show_alert({ message: __("{0} snapshot rows written", [r.message]), indicator: "green" });
						this.load(true);
					}),
			__("Rebuild KPI snapshots")
		);
	}

	on_show() {
		if (this.dashboard === "stage" && this.filters && this.stage_slug() !== this.filters.stage_slug) {
			this.filters.stage_slug = this.stage_slug();
			this.make_filter_bar();
			this.load();
		} else if (this.meta) {
			this.renderer.resize();
			this.schedule();
		}
	}
}
