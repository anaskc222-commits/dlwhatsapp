"""
Whitelisted API endpoints for the chat page and form integrations.
"""
import json
import frappe
from frappe import _
from frappe.utils import cint

from dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_account.dl_whatsapp_account import (
    get_default_account,
)
from dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_contact.dl_whatsapp_contact import (
    normalize_phone,
)


@frappe.whitelist()
def send_message(to, message, content_type="text", attach=None, reply_to=None, account=None):
    """Send a WhatsApp message — called from chat page."""
    frappe.has_permission("DL WhatsApp Message", "create", throw=True)

    doc_data = {
        "doctype": "DL WhatsApp Message",
        "type": "Outgoing",
        "to": normalize_phone(to),
        "content_type": content_type,
        "message": message,
        "attach": attach,
        "account": account,
    }
    if reply_to:
        doc_data["is_reply"] = 1
        doc_data["reply_to_message_id"] = reply_to

    msg = frappe.get_doc(doc_data).insert()
    return {"name": msg.name, "message_id": msg.message_id, "status": msg.status}


@frappe.whitelist()
def send_template(to, template, reference_doctype=None, reference_name=None,
                  custom_params=None, account=None):
    """Send a WhatsApp template message — callable from any form."""
    frappe.has_permission("DL WhatsApp Message", "create", throw=True)

    params = None
    if custom_params:
        params = custom_params if isinstance(custom_params, str) else json.dumps(custom_params)
    elif reference_doctype and reference_name:
        tpl = frappe.get_doc("DL WhatsApp Template", template)
        if tpl.field_names:
            ref_doc = frappe.get_doc(reference_doctype, reference_name)
            vals = [str(ref_doc.get(f.strip()) or "") for f in tpl.field_names.split(",")]
            params = json.dumps(vals)

    doc_data = {
        "doctype": "DL WhatsApp Message",
        "type": "Outgoing",
        "to": normalize_phone(to),
        "content_type": "template",
        "template": template,
        "template_parameters": params,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "account": account,
    }
    msg = frappe.get_doc(doc_data).insert()
    return {"name": msg.name, "message_id": msg.message_id, "status": msg.status}


@frappe.whitelist()
def send_document_pdf(to, doctype, docname, print_format=None, template=None, account=None, caption=None):
    """Generate PDF for a document and send it as a WhatsApp attachment."""
    frappe.has_permission(doctype, "print", docname, throw=True)

    fmt_row = _get_pdf_format_row(doctype)
    if not print_format:
        print_format = fmt_row.get("print_format") if fmt_row else None

    if not caption:
        caption = (fmt_row.get("message_caption") if fmt_row else None) or docname

    pdf_data = frappe.get_print(doctype, docname, print_format, as_pdf=True)
    fname = f"{docname}.pdf"

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": fname,
        "content": pdf_data,
        "is_private": 0,
    }).insert(ignore_permissions=True)

    if template:
        send_template(to, template, reference_doctype=doctype,
                      reference_name=docname, account=account)

    doc_data = {
        "doctype": "DL WhatsApp Message",
        "type": "Outgoing",
        "to": normalize_phone(to),
        "content_type": "document",
        "message": caption,
        "attach": file_doc.file_url,
        "reference_doctype": doctype,
        "reference_name": docname,
        "account": account,
    }
    msg = frappe.get_doc(doc_data).insert()
    return {"name": msg.name, "file_url": file_doc.file_url, "status": msg.status}


@frappe.whitelist()
def get_pdf_print_format(doctype):
    """Return the default print format and caption configured for a doctype."""
    row = _get_pdf_format_row(doctype)
    if row:
        return {"print_format": row.get("print_format"), "caption": row.get("message_caption")}
    return {}


def _get_pdf_format_row(doctype):
    """Look up the DL WhatsApp PDF Format child table for a given doctype."""
    try:
        rows = frappe.get_all(
            "DL WhatsApp PDF Format",
            filters={"parent": "DL WhatsApp Settings", "document_type": doctype},
            fields=["print_format", "message_caption"],
            limit=1,
        )
        return rows[0] if rows else {}
    except Exception:
        return {}


@frappe.whitelist()
def get_messages(contact, limit=50, before=None):
    """Fetch paginated messages for a contact (for chat page)."""
    frappe.has_permission("DL WhatsApp Message", "read", throw=True)
    phone = normalize_phone(contact)

    filters = [
        ["DL WhatsApp Message", "contact", "=", phone],
    ]
    if before:
        filters.append(["DL WhatsApp Message", "creation", "<", before])

    messages = frappe.get_all(
        "DL WhatsApp Message",
        filters=filters,
        fields=[
            "name", "type", "status", "content_type", "message",
            "attach", "media_mime_type", "message_id", "is_reply",
            "reply_to_message_id", "creation", "template",
        ],
        order_by="creation asc",
        limit=cint(limit),
    )
    return messages


@frappe.whitelist()
def get_contacts(search=None, limit=30):
    """Fetch contact list with unread counts for chat sidebar."""
    frappe.has_permission("DL WhatsApp Contact", "read", throw=True)

    filters = {}
    if search:
        filters = [
            ["DL WhatsApp Contact", "contact_name", "like", f"%{search}%"],
            ["DL WhatsApp Contact", "phone", "like", f"%{search}%"],
        ]

    contacts = frappe.get_all(
        "DL WhatsApp Contact",
        filters=filters if isinstance(filters, dict) else None,
        or_filters=filters if isinstance(filters, list) else None,
        fields=[
            "name", "phone", "contact_name", "profile_picture",
            "last_message", "last_message_time", "unread_count",
        ],
        order_by="last_message_time desc",
        limit=cint(limit),
    )
    return contacts


@frappe.whitelist()
def mark_contact_read(contact):
    """Reset unread count for a contact."""
    phone = normalize_phone(contact)
    if frappe.db.exists("DL WhatsApp Contact", phone):
        frappe.db.set_value("DL WhatsApp Contact", phone, "unread_count", 0)
    return True


@frappe.whitelist()
def get_templates(doctype=None):
    """Return approved templates for a doctype (for send dialog)."""
    filters = {"status": "Approved"}
    if doctype:
        filters_list = [
            ["DL WhatsApp Template", "status", "=", "Approved"],
            ["DL WhatsApp Template", "for_doctype", "in", [doctype, ""]],
        ]
        return frappe.get_all(
            "DL WhatsApp Template",
            filters=filters_list,
            fields=["name", "template_name", "category", "body_text", "language_code"],
        )
    return frappe.get_all(
        "DL WhatsApp Template",
        filters=filters,
        fields=["name", "template_name", "category", "body_text", "language_code"],
    )


@frappe.whitelist()
def ensure_contact(phone, contact_name=None):
    """Create contact if not exists — called from New Chat dialog."""
    from dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_contact.dl_whatsapp_contact import get_or_create_contact
    phone = normalize_phone(phone)
    get_or_create_contact(phone, name=contact_name)
    return phone


@frappe.whitelist()
def test_connection(account=None):
    """Test API connection to Meta."""
    try:
        if account:
            acc = frappe.get_doc("DL WhatsApp Account", account)
        else:
            acc = get_default_account()
        if not acc:
            return {"success": False, "error": "No account configured"}
        import requests
        token = acc.get_password("token")
        url = f"{acc.url or 'https://graph.facebook.com'}/{acc.version or 'v21.0'}/{acc.phone_id}"
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.ok:
            return {"success": True, "data": r.json()}
        return {"success": False, "error": r.json().get("error", {}).get("message", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def sync_templates(account=None):
    """Fetch templates from Meta Business API and upsert locally."""
    try:
        if account:
            acc = frappe.get_doc("DL WhatsApp Account", account)
        else:
            acc = get_default_account()
        if not acc or not acc.business_id:
            frappe.throw(_("Business Account ID is required to sync templates"))

        import requests
        token = acc.get_password("token")
        url = (
            f"{acc.url or 'https://graph.facebook.com'}/{acc.version or 'v21.0'}"
            f"/{acc.business_id}/message_templates"
        )
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if not r.ok:
            frappe.throw(r.json().get("error", {}).get("message", "Sync failed"))

        templates = r.json().get("data", [])
        for tpl in templates:
            name = tpl.get("name")
            if not name:
                continue
            existing = frappe.db.exists("DL WhatsApp Template", name)
            body_text = ""
            for comp in tpl.get("components", []):
                if comp.get("type") == "BODY":
                    body_text = comp.get("text", "")

            if existing:
                frappe.db.set_value("DL WhatsApp Template", name, {
                    "status": tpl.get("status", "").capitalize(),
                    "body_text": body_text,
                    "meta_template_id": tpl.get("id"),
                })
            else:
                frappe.get_doc({
                    "doctype": "DL WhatsApp Template",
                    "template_name": name,
                    "language_code": tpl.get("language"),
                    "category": tpl.get("category", "UTILITY"),
                    "status": tpl.get("status", "Pending").capitalize(),
                    "body_text": body_text,
                    "meta_template_id": tpl.get("id"),
                    "account": acc.name,
                }).insert(ignore_permissions=True)

        frappe.db.commit()
        return True
    except Exception as e:
        frappe.log_error("DL WhatsApp Sync Templates", frappe.get_traceback())
        frappe.throw(str(e))
