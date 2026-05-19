import json
import frappe
from frappe.model.document import Document


class DLWhatsAppNotification(Document):
    pass


def trigger_notifications(doc, event):
    """Called from doc_events hook for all doctypes."""
    try:
        if not frappe.db.table_exists("tabDL WhatsApp Settings"):
            return
        settings = frappe.get_single("DL WhatsApp Settings")
        if not settings.enable_notifications:
            return
    except Exception:
        return

    notifications = frappe.get_all(
        "DL WhatsApp Notification",
        filters={"enabled": 1, "document_type": doc.doctype, "event": event},
        fields=["name", "phone_field", "static_phone", "recipient_type",
                "template", "field_names", "conditions"],
    )
    for n in notifications:
        try:
            _fire(doc, n)
        except Exception:
            frappe.log_error(f"DL WhatsApp Notification Error: {n.name}", frappe.get_traceback())


def _fire(doc, notification):
    # Evaluate conditions
    if notification.get("conditions"):
        try:
            result = frappe.safe_eval(notification["conditions"], eval_globals={"doc": doc})
            if not result:
                return
        except Exception:
            return

    # Determine recipient phone
    phone = None
    if notification["recipient_type"] == "Field":
        phone = doc.get(notification["phone_field"])
    else:
        phone = notification["static_phone"]

    if not phone:
        return

    # Build template parameters from doc fields
    tpl_params = []
    if notification.get("field_names"):
        for field in notification["field_names"].split(","):
            field = field.strip()
            val = doc.get(field)
            tpl_params.append(str(val) if val is not None else "")

    frappe.get_doc({
        "doctype": "DL WhatsApp Message",
        "type": "Outgoing",
        "to": str(phone),
        "content_type": "template",
        "template": notification["template"],
        "template_parameters": json.dumps(tpl_params) if tpl_params else None,
        "reference_doctype": doc.doctype,
        "reference_name": doc.name,
    }).insert(ignore_permissions=True)
