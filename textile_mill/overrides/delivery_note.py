"""Delivery Note hooks: keep the Carton Packing List link in step (Part D §D6.3)."""

import frappe


def release_packing_list(doc, method=None) -> None:
	name = doc.get("dm_carton_packing_list")
	if name and frappe.db.get_value("Carton Packing List", name, "delivery_note") == doc.name:
		frappe.db.set_value("Carton Packing List", name, "delivery_note", None)
