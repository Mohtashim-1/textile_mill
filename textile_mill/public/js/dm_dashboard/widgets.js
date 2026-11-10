import * as C from "./charts";
import { delta_class, download, fmt, open_route, rag_color, to_csv } from "./format";

const esc = (s) => frappe.utils.escape_html(s === null || s === undefined ? "" : String(s));

export class WidgetRenderer {
	constructor(dashboard) {
		this.dash = dashboard;
		this.charts = [];
	}

	get currency() {
		return this.dash.meta?.currency;
	}

	dispose() {
		this.charts.forEach((c) => c.dispose());
		this.charts = [];
	}

	resize() {
		this.charts.forEach((c) => c.resize());
	}

	chart(el, option, on_click) {
		const chart = C.echarts.init(el, null, { renderer: "canvas" });
		chart.setOption(option);
		if (on_click) chart.on("click", on_click);
		this.charts.push(chart);
		return chart;
	}

	// ------------------------------------------------------------ KPI tiles
	tile(t) {
		const status = t.target?.status || "neutral";
		const delta = t.compare ? t.compare.delta_pct : null;
		const cls = delta_class(delta, t.direction);
		const arrow = delta === null ? "" : delta > 0.05 ? "▲" : delta < -0.05 ? "▼" : "■";
		const unit = t.unit && t.format !== "currency" ? `<span class="dm-unit">${esc(t.unit)}</span>` : "";
		const $t = $(`
			<div class="dm-tile dm-rag-${status} ${t.drilldown ? "dm-click" : ""}" title="${esc(t.tooltip || "")}">
				<div class="dm-tile-label">${esc(__(t.label))}</div>
				<div class="dm-tile-value">${fmt(t.value, t.format, this.currency)}${unit}</div>
				<div class="dm-tile-meta">
					${t.compare ? `<span class="dm-delta dm-${cls}">${arrow} ${Math.abs(delta).toFixed(1)}%</span><span class="dm-basis">${esc(__("vs {0}", [__(t.compare.basis)]))}</span>` : ""}
					${t.target ? `<span class="dm-target">${__("Target")} ${fmt(t.target.value, t.format, this.currency)}</span>` : ""}
					${t.standard ? `<span class="dm-target">${esc(t.standard.label)} ${fmt(t.standard.value, t.format, this.currency)}</span>` : ""}
				</div>
				${t.subtitle ? `<div class="dm-tile-sub">${esc(t.subtitle)}</div>` : ""}
				<div class="dm-spark"></div>
			</div>`);
		if (t.drilldown) $t.on("click", () => open_route(t.drilldown));
		const spark = $t.find(".dm-spark")[0];
		if (t.spark && t.spark.length > 1) {
			requestAnimationFrame(() => this.chart(spark, C.spark(t.spark, status)));
		} else {
			$(spark).remove();
		}
		return $t;
	}

	// ------------------------------------------------------------ widget card
	card(w) {
		const $card = $(`
			<div class="dm-card dm-span-${w.span || 6}" data-widget="${esc(w.id)}">
				<div class="dm-card-head">
					<div class="dm-card-title">${esc(__(w.title))}
						${w.synthetic ? `<span class="dm-badge dm-sample" title="${__("Includes generated history before go-live")}">${__("Sample history")}</span>` : ""}
						${w.explain ? `<span class="dm-info" title="${esc(w.explain)}">i</span>` : ""}
					</div>
					<div class="dm-card-actions">
						${this.exportable(w) ? `<button class="btn btn-xs btn-default dm-csv" title="${__("Export CSV")}">CSV</button>` : ""}
						${w.drilldown ? `<button class="btn btn-xs btn-default dm-open" title="${__("Open")}">↗</button>` : ""}
					</div>
				</div>
				<div class="dm-card-body"></div>
				${w.note ? `<div class="dm-note">${esc(w.note)}</div>` : ""}
			</div>`);
		$card.find(".dm-csv").on("click", () => this.export(w));
		$card.find(".dm-open").on("click", () => open_route(w.drilldown));
		const body = $card.find(".dm-card-body");
		const render = this[w.type];
		if (render) {
			requestAnimationFrame(() => render.call(this, body, w.data, w));
		} else {
			body.html(`<div class="dm-empty">${esc(w.note || __("Not available"))}</div>`);
		}
		return $card;
	}

	exportable(w) {
		return ["table", "bar", "grouped_bar", "stacked_bar", "line", "combo", "pareto", "donut", "status_bars"].includes(w.type);
	}

	export(w) {
		const d = w.data;
		let columns = [];
		let rows = [];
		if (w.type === "table") {
			columns = d.columns.map((c) => c.label);
			rows = d.rows.map((r) => d.columns.map((c) => r[c.field]));
		} else if (w.type === "pareto") {
			columns = [__("Category"), __("Value"), __("Cumulative %")];
			rows = d.categories.map((c, i) => [c, d.values[i], d.cumulative[i]]);
		} else if (w.type === "donut" || w.type === "status_bars") {
			columns = [__("Name"), __("Value")];
			rows = d.items.map((i) => [i.name, i.value]);
		} else {
			columns = [__("Category"), ...d.series.map((s) => s.name)];
			rows = d.categories.map((c, i) => [c, ...d.series.map((s) => s.values[i])]);
		}
		download(`${w.id}-${frappe.datetime.now_date()}.csv`, to_csv(columns, rows));
	}

	empty(body, w) {
		body.html(`<div class="dm-empty">${esc(w?.note || __("No data for the selected period."))}</div>`);
	}

	// ------------------------------------------------------------ chart widgets
	_cartesian(body, d, w) {
		if (!d.categories?.length || !d.series?.some((s) => s.values.some((v) => v !== null && v !== undefined))) return this.empty(body, w);
		const el = $(`<div class="dm-chart"></div>`).appendTo(body)[0];
		this.chart(el, C.cartesian(w.type, d, this.currency));
	}
	bar(body, d, w) {
		this._cartesian(body, d, w);
	}
	grouped_bar(body, d, w) {
		this._cartesian(body, d, w);
	}
	stacked_bar(body, d, w) {
		this._cartesian(body, d, w);
	}
	line(body, d, w) {
		this._cartesian(body, d, w);
	}
	combo(body, d, w) {
		this._cartesian(body, d, w);
	}
	pareto(body, d, w) {
		if (!d.categories?.length) return this.empty(body, w);
		this.chart($(`<div class="dm-chart"></div>`).appendTo(body)[0], C.pareto(d, this.currency));
	}
	waterfall(body, d, w) {
		this.chart($(`<div class="dm-chart"></div>`).appendTo(body)[0], C.waterfall(d, this.currency));
	}
	donut(body, d, w) {
		if (!d.items?.some((i) => i.value)) return this.empty(body, w);
		this.chart($(`<div class="dm-chart"></div>`).appendTo(body)[0], C.donut(d, this.currency));
	}
	heatmap(body, d, w) {
		if (!d.data?.length) return this.empty(body, w);
		const height = Math.max(220, d.y.length * 22 + 60);
		this.chart($(`<div class="dm-chart" style="height:${height}px"></div>`).appendTo(body)[0], C.heatmap(d));
	}
	scatter(body, d, w) {
		if (!d.points?.length) return this.empty(body, w);
		this.chart($(`<div class="dm-chart"></div>`).appendTo(body)[0], C.scatter(d, this.currency), (p) => open_route(p.data.route));
	}
	gauge(body, d, w) {
		const el = $(`<div class="dm-gauge-one"></div>`).appendTo(body)[0];
		this.chart(el, C.gauge(d, this.currency));
	}
	gauge_group(body, d) {
		const $wrap = $(`<div class="dm-gauges"></div>`).appendTo(body);
		d.gauges.forEach((g) => {
			const $g = $(`<div class="dm-gauge ${g.route ? "dm-click" : ""}"><div class="dm-gauge-chart"></div><div class="dm-gauge-label">${esc(g.name)}</div></div>`).appendTo($wrap);
			if (g.route) $g.on("click", () => open_route(g.route));
			this.chart($g.find(".dm-gauge-chart")[0], C.gauge(g, this.currency));
		});
	}

	// ------------------------------------------------------------ HTML widgets
	table(body, d, w) {
		if (!d.rows?.length) return this.empty(body, w);
		const head = d.columns.map((c) => `<th class="${["currency", "float", "int", "percent"].includes(c.format) ? "text-right" : ""}">${esc(__(c.label))}</th>`).join("");
		const rows = d.rows
			.map((r, ri) => {
				const cells = d.columns
					.map((c) => {
						const status = r._status?.[c.field];
						const numeric = ["currency", "float", "int", "percent"].includes(c.format);
						const value = c.format === "link" || c.format === "data" || !c.format ? esc(r[c.field] ?? "") : fmt(r[c.field], c.format, this.currency, { full: true });
						const link = r._route?.[c.field] ? `<a class="dm-link" data-row="${ri}" data-field="${esc(c.field)}">${value}</a>` : value;
						return `<td class="${numeric ? "text-right" : ""} ${status ? "dm-cell-" + status : ""}">${link}</td>`;
					})
					.join("");
				const action = r._action ? `<td><button class="btn btn-xs btn-default dm-action" data-row="${ri}">${esc(__(r._action.label))}</button></td>` : "";
				return `<tr>${cells}${action}</tr>`;
			})
			.join("");
		const has_action = d.rows.some((r) => r._action);
		const $t = $(`<div class="dm-table-wrap"><table class="dm-table"><thead><tr>${head}${has_action ? "<th></th>" : ""}</tr></thead><tbody>${rows}</tbody></table></div>`).appendTo(body);
		$t.on("click", ".dm-link", (e) => {
			const r = d.rows[$(e.currentTarget).data("row")];
			open_route(r._route[$(e.currentTarget).data("field")]);
		});
		$t.on("click", ".dm-action", (e) => {
			const a = d.rows[$(e.currentTarget).data("row")]._action;
			if (a.role && !frappe.user.has_role(a.role)) {
				frappe.msgprint(__("Only {0} can do this.", [__(a.role)]));
				return;
			}
			frappe.confirm(__("{0} for {1}?", [__(a.label), a.args.item_code]), () =>
				frappe.call({ method: a.method, args: a.args, freeze: true }).then((res) => {
					frappe.show_alert({ message: __("Created {0}", [res.message]), indicator: "green" });
					frappe.set_route("Form", "Material Request", res.message);
				})
			);
		});
	}

	status_bars(body, d, w) {
		if (!d.items?.length) return this.empty(body, w);
		const max = Math.max(...d.items.map((i) => i.value), 1);
		const html = d.items
			.map(
				(i) => `<div class="dm-sbar ${i.route ? "dm-click" : ""}" data-name="${esc(i.name)}">
					<div class="dm-sbar-label">${esc(__(i.name))}</div>
					<div class="dm-sbar-track"><div class="dm-sbar-fill dm-st-${frappe.scrub(i.name)}" style="width:${(i.value / max) * 100}%"></div></div>
					<div class="dm-sbar-value">${fmt(i.value, d.format, this.currency)}${i.pct !== undefined ? ` <span class="dm-muted">${i.pct}%</span>` : ""}${d.show_qty && i.qty !== undefined ? ` <span class="dm-muted">· ${fmt(i.qty, "float")}</span>` : ""}</div>
				</div>`
			)
			.join("");
		const $w = $(`<div class="dm-sbars">${html}</div>`).appendTo(body);
		$w.on("click", ".dm-sbar.dm-click", (e) => {
			const item = d.items.find((i) => i.name === $(e.currentTarget).data("name"));
			open_route(item.route);
		});
	}

	alert_list(body, d) {
		if (!d.items?.length) {
			body.html(`<div class="dm-empty dm-ok">✓ ${esc(d.empty || __("No alerts"))}</div>`);
			return;
		}
		const html = d.items
			.map((a, i) => `<li class="dm-alert dm-alert-${a.level} ${a.route ? "dm-click" : ""}" data-i="${i}"><span class="dm-dot"></span>${esc(a.text)}</li>`)
			.join("");
		const $l = $(`<ul class="dm-alerts">${html}</ul>`).appendTo(body);
		$l.on("click", ".dm-click", (e) => open_route(d.items[$(e.currentTarget).data("i")].route));
	}

	calendar_strip(body, d) {
		const html = d.days
			.map(
				(day) => `<div class="dm-day ${day.status ? "dm-day-" + day.status : ""}" title="${esc(day.tooltip || "")}">
					<div class="dm-dow">${esc(day.dow)}</div><div class="dm-dnum">${esc(day.label)}</div>
					<div class="dm-dcount">${day.count ? day.count : ""}</div></div>`
			)
			.join("");
		body.html(`<div class="dm-calendar">${html}</div>`);
	}

	value_chain_flow(body, d) {
		const rows = d.rows || [{ nodes: d.nodes, links: d.links }];
		rows.forEach((row) => {
			if (rows.length > 1 && row.title) $(`<div class="dm-flow-caption">${esc(__(row.title))}</div>`).appendTo(body);
			this.value_chain_row(body, row);
		});
	}

	value_chain_row(body, d) {
		const nodes = d.nodes
			.map((n, i) => {
				const arrow = i < d.nodes.length - 1 ? `<div class="dm-flow-arrow"><span>${fmt(d.links[i]?.value, "float")}</span>→</div>` : "";
				const y = n.yield_pct === null || n.yield_pct === undefined ? "—" : n.yield_label === "yield" ? fmt(n.yield_pct, "percent") : `${fmt(n.yield_pct, "float")} ${esc(n.yield_label)}`;
				return `<div class="dm-flow-node dm-rag-${n.status} dm-click" data-route="${esc(n.route)}">
						<div class="dm-flow-title">${esc(__(n.label))}</div>
						<div class="dm-flow-out">${fmt(n.output, "float")} <span class="dm-unit">${esc(n.uom || "")}</span></div>
						<div class="dm-flow-row"><span>${__("Yield")}</span><b style="color:${rag_color(n.status)}">${y}</b></div>
						<div class="dm-flow-row"><span>${__("Cost/unit")}</span><b>${fmt(n.cost_per_unit, "currency", this.currency)}</b></div>
						<div class="dm-flow-row"><span>${__("Waiting")}</span><b>${fmt(n.wip_qty, "float")} ${esc(n.wip_uom || "")}</b></div>
					</div>${arrow}`;
			})
			.join("");
		const $f = $(`<div class="dm-flow">${nodes}</div>`).appendTo(body);
		$f.on("click", ".dm-flow-node", (e) => open_route($(e.currentTarget).data("route")));
	}

	error(body, d, w) {
		body.html(`<div class="dm-empty dm-error">${esc(w.note)}</div>`);
	}
}
