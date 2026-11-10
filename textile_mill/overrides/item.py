"""Item hooks (Part D §D2)."""

from frappe.utils import flt


def validate(doc, method=None) -> None:
	weight = flt(doc.get("dm_target_weight_kg"))
	doc.dm_pieces_per_kg = flt(1 / weight, 3) if weight > 0 else 0
