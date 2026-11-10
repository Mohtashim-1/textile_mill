"""Jinja helpers for Textile Mill print formats."""

import io

import frappe
from frappe.utils import flt
from markupsafe import Markup


def textile_qr(data: str, scale: int = 3) -> Markup:
	"""Inline SVG QR code (renders in browser print and wkhtmltopdf)."""
	import pyqrcode

	buffer = io.BytesIO()
	pyqrcode.create(str(data or ""), error="M").svg(buffer, scale=scale, xmldecl=False, svgns=True, quiet_zone=2)
	return Markup(buffer.getvalue().decode())


def roll_lot(batch_no: str) -> str | None:
	"""Finished lot a graded roll was cut from."""
	source = frappe.db.get_value("Batch", batch_no, ["dm_source_doctype", "dm_source_doc"], as_dict=True)
	if source and source.dm_source_doctype == "Fabric Roll Inspection":
		return frappe.db.get_value("Fabric Roll Inspection", source.dm_source_doc, "lot_batch")
	return None


def batch_qty(batch_no: str) -> float:
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	return flt(get_batch_qty(batch_no=batch_no))


def customer_label_spec(item_code: str, customer: str) -> dict:
	spec = frappe.db.get_value(
		"Customer Label Spec",
		{"parenttype": "Item", "parent": item_code, "customer": customer},
		["ean_barcode", "pcs_per_carton", "carton_marks"],
		as_dict=True,
	)
	ref_code = frappe.db.get_value("Item Customer Detail", {"parent": item_code, "customer_name": customer}, "ref_code")
	return {**(spec or {}), "customer_item_code": ref_code}


# ---------------------------------------------------------------- GS1 / Code 128
# Code 128 bar/space widths for symbol values 0–106 (106 = stop, 7 elements).
_C128 = (
	"212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 "
	"113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 "
	"212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 "
	"113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 "
	"314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 "
	"241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 "
	"214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 "
	"211232 2331112"
).split()
_START_B, _START_C, _CODE_B, _CODE_C, _FNC1 = 104, 105, 100, 99, 102


def _code128_values(data: str, gs1: bool = False) -> list[int]:
	"""Symbol values (start…check) using Code C for digit pairs and Code B otherwise."""
	values, i, mode = [], 0, None

	def digit_run(pos: int) -> int:
		n = pos
		while n < len(data) and data[n].isdigit():
			n += 1
		return n - pos

	if digit_run(0) >= 4 or (gs1 and digit_run(0) >= 2):
		values.append(_START_C)
		mode = "C"
	else:
		values.append(_START_B)
		mode = "B"
	if gs1:
		values.append(_FNC1)
	while i < len(data):
		run = digit_run(i)
		if mode == "C" and run >= 2:
			values.append(int(data[i : i + 2]))
			i += 2
			continue
		if mode == "B" and run >= 4 and run % 2 == 0:
			values.append(_CODE_C)
			mode = "C"
			continue
		if mode == "C":
			values.append(_CODE_B)
			mode = "B"
		values.append(ord(data[i]) - 32)
		i += 1
	check = (values[0] + sum(v * pos for pos, v in enumerate(values[1:], start=1))) % 103
	return [*values, check, 106]


def code128_svg(data: str, height: int = 60, module: float = 1.6, gs1: bool = False, text: str | None = None) -> Markup:
	"""Inline SVG Code 128 (GS1-128 when gs1=True, e.g. AI (00) SSCC labels)."""
	data = str(data or "")
	widths = "".join(_C128[v] for v in _code128_values(data, gs1)) if data else ""
	quiet = 10
	x, bars = quiet * module, []
	for idx, w in enumerate(widths):
		width = int(w) * module
		if idx % 2 == 0:
			bars.append(f'<rect x="{x:.2f}" y="0" width="{width:.2f}" height="{height}"/>')
		x += width
	total = x + quiet * module
	label = text if text is not None else data
	return Markup(
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total:.2f} {height + 16}" '
		f'width="{total:.0f}" height="{height + 16}" class="tm-barcode"><g fill="#000">{"".join(bars)}</g>'
		f'<text x="{total / 2:.2f}" y="{height + 13}" font-size="12" text-anchor="middle" '
		f'font-family="monospace">{frappe.utils.escape_html(label)}</text></svg>'
	)


def gs1_check_digit(digits: str) -> int:
	"""GS1 mod-10: weights 3,1,3… from the rightmost digit."""
	total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
	return (10 - total % 10) % 10


def make_sscc(company_prefix: str, serial: int, extension: int = 0) -> str:
	"""18-digit SSCC = extension + company prefix + serial reference (padded to 17) + check digit."""
	body = f"{extension}{company_prefix}"
	body += str(serial).zfill(17 - len(body))
	if len(body) != 17:
		frappe.throw(f"SSCC serial {serial} does not fit after prefix {company_prefix}")
	return body + str(gs1_check_digit(body))
