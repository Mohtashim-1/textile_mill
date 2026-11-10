"""Dye Recipe Approval workflow (Part B §5.3)."""

import frappe

WORKFLOW = "Dye Recipe Approval"
STATES = [
	# state, docstatus, allow_edit, style
	("Draft", 0, "Dyeing User", ""),
	("Lab Approved", 0, "Dye Lab Manager", "Info"),
	("Production Approved", 1, "Production Director", "Success"),
	("Obsolete", 1, "Production Director", "Inverse"),
]
TRANSITIONS = [
	# state, action, next_state, allowed
	("Draft", "Approve", "Lab Approved", "Dye Lab Manager"),
	("Lab Approved", "Reject", "Draft", "Dye Lab Manager"),
	("Lab Approved", "Approve", "Production Approved", "Production Director"),
	("Lab Approved", "Reject", "Draft", "Production Director"),
	("Production Approved", "Mark Obsolete", "Obsolete", "Production Director"),
]
STYLES = {"Draft": "", "Lab Approved": "Info", "Production Approved": "Success", "Obsolete": "Inverse"}


def setup_workflow() -> None:
	for state, style in STYLES.items():
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style}).insert(
				ignore_permissions=True
			)
	for action in {t[1] for t in TRANSITIONS}:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)

	wf = frappe.get_doc("Workflow", WORKFLOW) if frappe.db.exists("Workflow", WORKFLOW) else frappe.new_doc("Workflow")
	wf.update(
		{
			"workflow_name": WORKFLOW,
			"document_type": "Dye Recipe",
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 0,
			"override_status": 0,
		}
	)
	wf.set("states", [{"state": s, "doc_status": str(d), "allow_edit": r} for s, d, r, _ in STATES])
	wf.set(
		"transitions",
		[{"state": s, "action": a, "next_state": n, "allowed": r, "allow_self_approval": 1} for s, a, n, r in TRANSITIONS],
	)
	wf.save(ignore_permissions=True)
