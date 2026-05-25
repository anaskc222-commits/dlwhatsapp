import json
import frappe
from frappe.model.document import Document


class DLWhatsAppNotification(Document):
    pass


def trigger_notifications(doc, event):
    """Called from doc_events hook for all doctypes on every save/submit/cancel."""
    if not _notifications_enabled():
        return

    events_to_fire = [event]

    # When on_update fires, also check if workflow_state changed
    if event == "on_update" and doc.get("workflow_state"):
        before = doc.get_doc_before_save()
        if before and before.get("workflow_state") != doc.get("workflow_state"):
            events_to_fire.append("on_workflow_action")

    for ev in events_to_fire:
        _run_notifications(doc, ev)


def trigger_assignment_notifications(doc, event):
    """Called when a ToDo (assignment) is created — fires on_assign notifications."""
    if not doc.reference_type or not doc.allocated_to:
        return
    # Only fire for fresh assignments, not reminders or system todos
    if doc.status != "Open" or not doc.reference_name:
        return
    if not _notifications_enabled():
        return

    notifications = frappe.get_all(
        "DL WhatsApp Notification",
        filters={"enabled": 1, "document_type": doc.reference_type, "event": "on_assign"},
        fields=["name", "template", "field_names", "conditions"],
    )
    if not notifications:
        return

    try:
        ref_doc = frappe.get_doc(doc.reference_type, doc.reference_name)
    except Exception:
        return

    phone = _get_user_phone(doc.allocated_to)
    if not phone:
        return

    for n in notifications:
        try:
            if _check_conditions(ref_doc, n):
                _send(ref_doc, n, phone)
        except Exception:
            frappe.log_error(f"DL WhatsApp Assignment Notification: {n.name}", frappe.get_traceback())


def _notifications_enabled():
    try:
        if not frappe.db.table_exists("tabDL WhatsApp Settings"):
            return False
        return frappe.get_single("DL WhatsApp Settings").enable_notifications
    except Exception:
        return False


def _run_notifications(doc, event):
    notifications = frappe.get_all(
        "DL WhatsApp Notification",
        filters={"enabled": 1, "document_type": doc.doctype, "event": event},
        fields=[
            "name", "recipient_type", "phone_field", "static_phone",
            "user_field", "role", "template", "field_names",
            "conditions", "workflow_state",
        ],
    )
    for n in notifications:
        try:
            _fire(doc, n, event)
        except Exception:
            frappe.log_error(f"DL WhatsApp Notification Error: {n.name}", frappe.get_traceback())


def _fire(doc, notification, event):
    # Workflow state filter — only fire if doc is in the specified state
    if event == "on_workflow_action" and notification.get("workflow_state"):
        if doc.get("workflow_state") != notification["workflow_state"]:
            return

    if not _check_conditions(doc, notification):
        return

    recipient_type = notification.get("recipient_type", "Field")
    phones = []

    if recipient_type == "Field":
        phone = doc.get(notification.get("phone_field") or "")
        if phone:
            phones.append(str(phone))

    elif recipient_type == "Static Number":
        if notification.get("static_phone"):
            phones.append(notification["static_phone"])

    elif recipient_type == "User Field":
        user = doc.get(notification.get("user_field") or "")
        if user:
            phone = _get_user_phone(user)
            if phone:
                phones.append(phone)

    elif recipient_type == "Role":
        phones = _get_phones_for_role(notification.get("role") or "")

    for phone in phones:
        _send(doc, notification, phone)


def _check_conditions(doc, notification):
    if not notification.get("conditions"):
        return True
    try:
        return bool(frappe.safe_eval(notification["conditions"], eval_globals={"doc": doc}))
    except Exception:
        return False


def _send(doc, notification, phone):
    tpl_params = []
    if notification.get("field_names"):
        for field in notification["field_names"].split(","):
            val = doc.get(field.strip())
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


def _get_user_phone(user):
    """Return mobile_no (or phone) from User record."""
    mobile = frappe.db.get_value("User", user, "mobile_no")
    if mobile:
        return mobile
    return frappe.db.get_value("User", user, "phone") or None


def _get_phones_for_role(role):
    """Return mobile_no for all enabled users with the given role."""
    if not role:
        return []
    rows = frappe.db.sql(
        """
        SELECT DISTINCT u.mobile_no
        FROM `tabUser` u
        JOIN `tabHas Role` hr ON hr.parent = u.name
        WHERE hr.role = %s
          AND u.enabled = 1
          AND u.name NOT IN ('Administrator', 'Guest')
          AND u.mobile_no IS NOT NULL
          AND u.mobile_no != ''
        """,
        role,
        as_dict=True,
    )
    return [r.mobile_no for r in rows]
