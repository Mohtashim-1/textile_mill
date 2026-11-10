export const RAG = { green: "var(--dm-green)", amber: "var(--dm-amber)", red: "var(--dm-red)", neutral: "var(--dm-muted)" };

export function css_var(name) {
	return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function palette() {
	return ["--dm-c1", "--dm-c2", "--dm-c3", "--dm-c4", "--dm-c5", "--dm-c6", "--dm-c7", "--dm-c8"].map(css_var);
}

export function rag_color(status) {
	return css_var({ green: "--dm-green", amber: "--dm-amber", red: "--dm-red" }[status] || "--dm-muted");
}

export function compact(value) {
	const abs = Math.abs(value);
	if (abs >= 1e7) return (value / 1e7).toFixed(abs >= 1e8 ? 1 : 2) + " Cr";
	if (abs >= 1e5) return (value / 1e5).toFixed(abs >= 1e6 ? 1 : 2) + " L";
	if (abs >= 1e3) return (value / 1e3).toFixed(1) + "k";
	return format_number(value, abs < 10 ? 2 : 0);
}

export function format_number(value, precision = 0) {
	return Number(value).toLocaleString(undefined, { minimumFractionDigits: precision, maximumFractionDigits: precision });
}

export function fmt(value, format, currency, opts = {}) {
	if (value === null || value === undefined || value === "" || Number.isNaN(value)) return "—";
	switch (format) {
		case "currency":
			return (currency ? currency + " " : "") + (opts.full ? format_number(value, 0) : compact(value));
		case "percent":
			return format_number(value, Math.abs(value) < 10 ? 1 : 1) + "%";
		case "int":
			return format_number(Math.round(value), 0);
		case "float":
			return opts.full ? format_number(value, 2) : compact(value);
		case "date":
			return frappe.datetime.str_to_user(value);
		default:
			return typeof value === "number" ? compact(value) : frappe.utils.escape_html(String(value));
	}
}

export function axis_formatter(format) {
	return (v) => (format === "percent" ? v + "%" : format === "currency" || Math.abs(v) >= 1000 ? compact(v) : v);
}

export function delta_class(delta, direction) {
	if (delta === null || delta === undefined || Math.abs(delta) < 0.05) return "flat";
	const good = direction === "Lower is better" ? delta < 0 : delta > 0;
	return good ? "good" : "bad";
}

export function to_csv(columns, rows) {
	const esc = (v) => {
		const s = v === null || v === undefined ? "" : String(v);
		return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
	};
	return [columns.map(esc).join(","), ...rows.map((r) => r.map(esc).join(","))].join("\n");
}

export function download(filename, text) {
	const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
	const a = document.createElement("a");
	a.href = URL.createObjectURL(blob);
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	setTimeout(() => {
		URL.revokeObjectURL(a.href);
		a.remove();
	}, 0);
}

export function open_route(target) {
	if (!target) return;
	if (typeof target === "string") {
		frappe.set_route(target.replace(/^\/app\//, "").split("/"));
		return;
	}
	if (Array.isArray(target)) {
		const last = target[target.length - 1];
		if (last && typeof last === "object") {
			frappe.route_options = last;
			frappe.set_route(...target.slice(0, -1));
		} else {
			frappe.set_route(...target);
		}
		return;
	}
	if (target.route) {
		frappe.route_options = target.filters || {};
		frappe.set_route(...target.route);
	}
}
