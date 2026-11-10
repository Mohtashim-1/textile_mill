import * as echarts from "echarts/core";
import { BarChart, GaugeChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
	GridComponent,
	LegendComponent,
	MarkLineComponent,
	TooltipComponent,
	VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { axis_formatter, css_var, fmt, palette, rag_color } from "./format";

echarts.use([
	BarChart,
	GaugeChart,
	HeatmapChart,
	LineChart,
	PieChart,
	ScatterChart,
	GridComponent,
	LegendComponent,
	MarkLineComponent,
	TooltipComponent,
	VisualMapComponent,
	CanvasRenderer,
]);

export { echarts };

function base(currency) {
	const text = css_var("--dm-text");
	const muted = css_var("--dm-muted");
	const line = css_var("--dm-grid");
	return {
		color: palette(),
		textStyle: { color: text, fontFamily: "inherit" },
		grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
		legend: { top: 0, textStyle: { color: muted }, itemWidth: 12, itemHeight: 8, type: "scroll" },
		tooltip: {
			trigger: "axis",
			backgroundColor: css_var("--dm-card"),
			borderColor: line,
			textStyle: { color: text },
			confine: true,
		},
		_axis: { line, muted, currency },
	};
}

function value_axis(opt, format, extra = {}) {
	return {
		type: "value",
		axisLabel: { color: opt._axis.muted, formatter: axis_formatter(format) },
		splitLine: { lineStyle: { color: opt._axis.line } },
		...extra,
	};
}

function category_axis(opt, categories, extra = {}) {
	return {
		type: "category",
		data: categories,
		axisLabel: { color: opt._axis.muted, hideOverlap: true },
		axisLine: { lineStyle: { color: opt._axis.line } },
		...extra,
	};
}

function mark_line(value) {
	if (value === null || value === undefined) return undefined;
	return {
		silent: true,
		symbol: "none",
		lineStyle: { color: css_var("--dm-amber"), type: "dashed" },
		label: { color: css_var("--dm-muted"), formatter: String(value) },
		data: [{ yAxis: value }],
	};
}

function value_tooltip(format, currency) {
	return (v) => fmt(Array.isArray(v) ? v[1] : v, format, currency);
}

export function cartesian(type, data, currency) {
	const opt = base(currency);
	const format = data.format || (data.unit === "%" ? "percent" : "float");
	const horizontal = !!data.horizontal;
	const cat = category_axis(opt, data.categories);
	const val = value_axis(opt, format);
	const dual = data.dual_axis || (data.series || []).some((s) => s.axis === 1);
	opt.tooltip.valueFormatter = value_tooltip(format, currency);
	opt.xAxis = horizontal ? val : cat;
	opt.yAxis = horizontal ? cat : dual ? [val, value_axis(opt, type === "combo" ? "percent" : format, { splitLine: { show: false } })] : val;
	opt.series = (data.series || []).map((s, i) => {
		let kind = s.type || (type === "line" ? "line" : "bar");
		const series = {
			name: s.name,
			type: kind,
			data: s.values,
			yAxisIndex: !horizontal && dual ? s.axis || 0 : 0,
			connectNulls: data.connect_nulls !== false,
			emphasis: { focus: "series" },
		};
		if (type === "stacked_bar" || s.stack) series.stack = s.stack || "total";
		if (kind === "line") {
			series.smooth = true;
			series.showSymbol = !!data.points || data.connect_nulls === false;
			series.symbolSize = 6;
			if (s.area) series.areaStyle = { opacity: 0.15 };
			if (s.dashed) series.lineStyle = { type: "dashed" };
			if (type === "combo" && s.axis === 1) series.tooltip = { valueFormatter: (v) => fmt(v, "percent") };
		}
		if (kind === "bar") {
			series.barMaxWidth = 28;
			if (data.threshold_low !== undefined || data.threshold_high !== undefined) {
				series.itemStyle = {
					color: (p) =>
						(data.threshold_low !== undefined && p.value < data.threshold_low) ||
						(data.threshold_high !== undefined && p.value > data.threshold_high)
							? rag_color("red")
							: palette()[0],
				};
			}
		}
		if (i === 0 && data.mark_line !== undefined && data.mark_line !== null) series.markLine = mark_line(data.mark_line);
		return series;
	});
	if (opt.series.length === 1) opt.legend.show = false;
	delete opt._axis;
	return opt;
}

export function pareto(data, currency) {
	const opt = base(currency);
	opt.xAxis = category_axis(opt, data.categories, { axisLabel: { color: opt._axis.muted, interval: 0, rotate: data.categories.length > 4 ? 30 : 0 } });
	opt.yAxis = [value_axis(opt, "float", { name: data.unit }), value_axis(opt, "percent", { max: 100, splitLine: { show: false } })];
	opt.series = [
		{ name: data.unit === "h" ? __("Hours") : __("Value"), type: "bar", data: data.values, barMaxWidth: 32 },
		{ name: __("Cumulative %"), type: "line", yAxisIndex: 1, data: data.cumulative, smooth: true, symbolSize: 6, tooltip: { valueFormatter: (v) => v + "%" } },
	];
	delete opt._axis;
	return opt;
}

export function waterfall(data, currency) {
	const opt = base(currency);
	const names = [data.start.name, ...data.steps.map((s) => s.name), data.end.name];
	const helper = [0];
	const up = [data.start.value];
	const down = [null];
	let running = data.start.value;
	for (const s of data.steps) {
		if (s.value >= 0) {
			helper.push(running);
			up.push(s.value);
			down.push(null);
		} else {
			helper.push(running + s.value);
			up.push(null);
			down.push(-s.value);
		}
		running += s.value;
	}
	helper.push(0);
	up.push(data.end.value);
	down.push(null);
	opt.xAxis = category_axis(opt, names, { axisLabel: { color: opt._axis.muted, interval: 0, rotate: 20 } });
	opt.yAxis = value_axis(opt, "currency");
	opt.legend.show = false;
	opt.tooltip.formatter = (params) => {
		const i = params[0].dataIndex;
		const v = i === 0 ? data.start.value : i === names.length - 1 ? data.end.value : data.steps[i - 1].value;
		return `${names[i]}: <b>${fmt(v, "currency", currency, { full: true })}</b>`;
	};
	const ends = (p) => (p.dataIndex === 0 || p.dataIndex === names.length - 1 ? palette()[0] : rag_color("red"));
	opt.series = [
		{ type: "bar", stack: "w", data: helper, itemStyle: { color: "transparent" }, emphasis: { disabled: true }, tooltip: { show: false } },
		{ name: __("Increase"), type: "bar", stack: "w", data: up, itemStyle: { color: ends }, barMaxWidth: 40 },
		{ name: __("Decrease"), type: "bar", stack: "w", data: down, itemStyle: { color: rag_color("green") }, barMaxWidth: 40 },
	];
	delete opt._axis;
	return opt;
}

export function donut(data, currency) {
	const opt = base(currency);
	const colors = { green: rag_color("green"), amber: rag_color("amber"), red: rag_color("red") };
	opt.tooltip = { ...opt.tooltip, trigger: "item", valueFormatter: (v) => fmt(v, data.format || "float", currency) + (data.unit ? " " + data.unit : "") };
	opt.legend = { ...opt.legend, top: "bottom" };
	opt.series = [
		{
			type: "pie",
			radius: ["48%", "72%"],
			center: ["50%", "45%"],
			avoidLabelOverlap: true,
			label: { formatter: "{d}%", color: css_var("--dm-text") },
			data: data.items.map((i) => ({ name: i.name, value: i.value, itemStyle: i.color ? { color: colors[i.color] } : undefined })),
		},
	];
	delete opt._axis;
	return opt;
}

export function gauge(g, currency) {
	const pct = g.max ? Math.max(0, Math.min(1, (g.value || 0) / g.max)) : 0;
	const color = g.status ? rag_color(g.status) : g.format === "percent" ? (g.value >= 85 ? rag_color("green") : g.value >= 60 ? rag_color("amber") : rag_color("red")) : palette()[0];
	return {
		series: [
			{
				type: "gauge",
				startAngle: 210,
				endAngle: -30,
				min: 0,
				max: 1,
				progress: { show: true, width: 10, itemStyle: { color } },
				axisLine: { lineStyle: { width: 10, color: [[1, css_var("--dm-grid")]] } },
				pointer: { show: false },
				axisTick: { show: false },
				splitLine: { show: false },
				axisLabel: { show: false },
				anchor: { show: false },
				title: { show: false },
				radius: "92%",
				detail: {
					valueAnimation: false,
					offsetCenter: [0, "5%"],
					fontSize: g.format === "currency" ? 13 : 16,
					fontWeight: 600,
					color: css_var("--dm-text"),
					formatter: () => (g.value === null || g.value === undefined ? "—" : fmt(g.value, g.format)),
				},
				data: [{ value: pct }],
			},
		],
	};
}

export function heatmap(data) {
	const opt = base();
	opt.tooltip = { ...opt.tooltip, trigger: "item", formatter: (p) => `${data.y[p.value[1]]} · ${data.x[p.value[0]]}: <b>${p.value[2]}%</b>` };
	opt.grid = { ...opt.grid, top: 8, bottom: 40 };
	opt.xAxis = category_axis(opt, data.x, { splitArea: { show: true } });
	opt.yAxis = category_axis(opt, data.y, { splitArea: { show: true } });
	opt.visualMap = {
		min: data.min,
		max: data.max,
		calculable: false,
		orient: "horizontal",
		left: "center",
		bottom: 0,
		itemHeight: 120,
		textStyle: { color: css_var("--dm-muted") },
		inRange: { color: [rag_color("red"), rag_color("amber"), rag_color("green")] },
	};
	opt.legend.show = false;
	opt.series = [{ type: "heatmap", data: data.data, label: { show: data.y.length <= 12, fontSize: 9 } }];
	delete opt._axis;
	return opt;
}

export function scatter(data, currency) {
	const opt = base(currency);
	const sizes = data.points.map((p) => p.size || 1);
	const max = Math.max(...sizes, 1);
	opt.tooltip = {
		...opt.tooltip,
		trigger: "item",
		formatter: (p) => `<b>${p.data.name}</b><br>${data.x_label}: ${fmt(p.data.value[0], data.x_format, currency)}<br>${data.y_label}: ${fmt(p.data.value[1], "percent")}`,
	};
	opt.xAxis = value_axis(opt, data.x_format || "float", { name: data.x_label, nameLocation: "middle", nameGap: 24 });
	opt.yAxis = value_axis(opt, "percent", { name: data.y_label });
	opt.legend.show = false;
	opt.series = [
		{
			type: "scatter",
			data: data.points.map((p) => ({ name: p.name, value: [p.x, p.y], route: p.route })),
			symbolSize: (_v, p) => 10 + 30 * Math.sqrt((data.points[p.dataIndex].size || 1) / max),
			label: { show: true, position: "top", formatter: (p) => p.data.name, fontSize: 10, color: css_var("--dm-muted") },
		},
	];
	delete opt._axis;
	return opt;
}

export function spark(values, status) {
	const color = status && status !== "neutral" ? rag_color(status) : palette()[0];
	return {
		animation: false,
		grid: { left: 0, right: 0, top: 2, bottom: 2 },
		xAxis: { type: "category", show: false, data: values.map((_v, i) => i) },
		yAxis: { type: "value", show: false, scale: true },
		series: [{ type: "line", data: values, smooth: true, symbol: "none", lineStyle: { width: 1.5, color }, areaStyle: { color, opacity: 0.12 } }],
	};
}
