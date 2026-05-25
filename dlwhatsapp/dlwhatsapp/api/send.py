"""
Whitelisted API endpoints for the chat page and form integrations.
"""
import json
import frappe
from frappe import _
from frappe.utils import cint, now_datetime, add_days

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

    phone = normalize_phone(to)

    # Text messages require an active 24h session (customer replied within last 24h).
    # If no session exists, send dlits_hello template and tell the frontend to wait.
    if content_type == "text" and not _has_active_session(phone):
        hello_sent = _send_welcome_if_configured(phone, account)
        return {
            "session_required": True,
            "hello_sent": hello_sent,
        }

    doc_data = {
        "doctype": "DL WhatsApp Message",
        "type": "Outgoing",
        "to": phone,
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
    """Generate PDF for a document and send it as a WhatsApp attachment.

    If a Document Template (with DOCUMENT header) is configured for this doctype in Settings,
    it is sent as a template message — this bypasses the 24-hour session requirement and
    works for initiating conversations with new contacts.
    """
    frappe.has_permission(doctype, "print", docname, throw=True)

    fmt_row = _get_pdf_format_row(doctype)
    if not print_format:
        print_format = fmt_row.get("print_format") if fmt_row else None
    if not caption:
        caption = (fmt_row.get("message_caption") if fmt_row else None) or docname

    # Use document template from Settings if not explicitly passed
    if not template and fmt_row:
        template = fmt_row.get("send_template")

    # Generate PDF and upload as public file
    pdf_data = frappe.get_print(doctype, docname, print_format, as_pdf=True)
    fname = f"{docname}.pdf"
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": fname,
        "content": pdf_data,
        "is_private": 0,
    }).insert(ignore_permissions=True)

    if template:
        # Send as a document-header template — no active session needed
        tpl_doc = frappe.get_doc("DL WhatsApp Template", template)
        # Build body params from the linked document fields
        body_params = _build_template_body_params(tpl_doc, doctype, docname, caption)

        doc_data = {
            "doctype": "DL WhatsApp Message",
            "type": "Outgoing",
            "to": normalize_phone(to),
            "content_type": "template",
            "template": template,
            "template_parameters": frappe.as_json(body_params),
            "attach": file_doc.file_url,
            "message": caption,
            "reference_doctype": doctype,
            "reference_name": docname,
            "account": account,
        }
    else:
        # Send as plain document — requires an active 24h session
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

    # Check for active 24-hour session before sending non-template document
    if doc_data.get("content_type") == "document":
        phone = normalize_phone(to)
        if not _has_active_session(phone):
            # No session — try welcome template if configured
            welcome_tpl = frappe.db.get_single_value("DL WhatsApp Settings", "welcome_template")
            if welcome_tpl:
                welcome = _send_welcome_if_configured(phone, account)
                if welcome:
                    return {
                        "welcome_sent": True,
                        "phone": phone,
                        "doctype": doctype,
                        "docname": docname,
                        "file_url": file_doc.file_url,
                        "message": _(
                            "No active conversation with this customer. "
                            "A welcome message has been sent. "
                            "Once they reply, open the chat to send the PDF."
                        ),
                    }
            # No template configured or welcome failed — inform the user
            frappe.throw(_(
                "No active WhatsApp conversation with this customer in the last 24 hours. "
                "Ask the customer to send any message to {0} first, "
                "then try again."
            ).format(
                frappe.db.get_value("DL WhatsApp Account",
                    frappe.db.get_single_value("DL WhatsApp Settings", "default_account") or account,
                    "phone_number") or "your WhatsApp number"
            ))

    msg = frappe.get_doc(doc_data).insert()
    return {"name": msg.name, "file_url": file_doc.file_url, "status": msg.status}


def _has_active_session(phone):
    """Return True if there is an incoming message from this contact within the last 24 hours."""
    cutoff = add_days(now_datetime(), -1)
    return frappe.db.exists(
        "DL WhatsApp Message",
        {"contact": phone, "type": "Incoming", "creation": [">", str(cutoff)]},
    )


def _send_welcome_if_configured(phone, account=None):
    """Send the welcome template to a contact if one is configured in Settings."""
    welcome_tpl = frappe.db.get_single_value("DL WhatsApp Settings", "welcome_template")
    if not welcome_tpl:
        return False
    try:
        # Pass contact name as {{1}} if the template uses variables
        contact_name = (
            frappe.db.get_value("DL WhatsApp Contact", phone, "contact_name") or phone
        )
        tpl_doc = frappe.get_doc("DL WhatsApp Template", welcome_tpl)
        params = None
        if "{{1}}" in (tpl_doc.body_text or "") or tpl_doc.field_names:
            params = frappe.as_json([contact_name])

        frappe.get_doc({
            "doctype": "DL WhatsApp Message",
            "type": "Outgoing",
            "to": phone,
            "content_type": "template",
            "template": welcome_tpl,
            "template_parameters": params,
            "account": account,
        }).insert(ignore_permissions=True)
        return True
    except Exception:
        frappe.log_error("DL WhatsApp Welcome Send Error", frappe.get_traceback())
        return False


def _build_template_body_params(tpl_doc, doctype, docname, fallback_caption):
    """Build body parameter list from template field_names or fallback to caption."""
    params = []
    if tpl_doc.field_names:
        try:
            ref_doc = frappe.get_doc(doctype, docname)
            for f in tpl_doc.field_names.split(","):
                params.append(str(ref_doc.get(f.strip()) or ""))
        except Exception:
            params = [fallback_caption]
    else:
        params = [fallback_caption]
    return params


@frappe.whitelist()
def get_pdf_print_format(doctype):
    """Return the default print format, template and caption configured for a doctype."""
    row = _get_pdf_format_row(doctype)
    if row:
        return {
            "print_format": row.get("print_format"),
            "caption": row.get("message_caption"),
            "send_template": row.get("send_template"),
        }
    return {}


def _get_pdf_format_row(doctype):
    """Look up the DL WhatsApp PDF Format child table for a given doctype."""
    try:
        rows = frappe.get_all(
            "DL WhatsApp PDF Format",
            filters={"parent": "DL WhatsApp Settings", "document_type": doctype},
            fields=["print_format", "message_caption", "send_template"],
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
        url = f"{acc.url or 'https://graph.facebook.com'}/{acc.version or 'v25.0'}/{acc.phone_id}"
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
            f"{acc.url or 'https://graph.facebook.com'}/{acc.version or 'v25.0'}"
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

            # Parse all components
            body_text = footer_text = header_text = header_type = ""
            for comp in tpl.get("components", []):
                ctype = comp.get("type", "").upper()
                if ctype == "BODY":
                    body_text = comp.get("text", "")
                elif ctype == "FOOTER":
                    footer_text = comp.get("text", "")
                elif ctype == "HEADER":
                    fmt = comp.get("format", "").upper()
                    header_type = fmt  # TEXT, IMAGE, DOCUMENT, VIDEO
                    if fmt == "TEXT":
                        header_text = comp.get("text", "")

            if existing:
                frappe.db.set_value("DL WhatsApp Template", name, {
                    "status": tpl.get("status", "").capitalize(),
                    "body_text": body_text,
                    "footer_text": footer_text,
                    "header_type": header_type,
                    "header_text": header_text,
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
                    "footer_text": footer_text,
                    "header_type": header_type,
                    "header_text": header_text,
                    "meta_template_id": tpl.get("id"),
                    "account": acc.name,
                }).insert(ignore_permissions=True)

        frappe.db.commit()
        return True
    except Exception as e:
        frappe.log_error("DL WhatsApp Sync Templates", frappe.get_traceback())
        frappe.throw(str(e))
