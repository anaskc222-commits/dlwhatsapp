import frappe
from frappe.model.document import Document


class DLWhatsAppLog(Document):
    pass


def write_log(log_type, payload, status=None, account=None, phone=None):
    try:
        frappe.get_doc({
            "doctype": "DL WhatsApp Log",
            "log_type": log_type,
            "status": status or "",
            "account": account,
            "phone": phone,
            "payload": payload if isinstance(payload, str) else frappe.as_json(payload),
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error("DL WhatsApp Log Write Error", frappe.get_traceback())
