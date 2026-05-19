"""
Meta WhatsApp Business API webhook handler.
Registered at: /api/method/dlwhatsapp.dlwhatsapp.api.webhook.handle
"""
import json
import frappe
import requests
from werkzeug.wrappers import Response

from dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_account.dl_whatsapp_account import (
    get_account_by_phone_id,
    get_default_account,
)
from dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_contact.dl_whatsapp_contact import (
    get_or_create_contact,
    normalize_phone,
)
from dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_log.dl_whatsapp_log import write_log


@frappe.whitelist(allow_guest=True)
def handle():
    if frappe.request.method == "GET":
        return _verify()
    return _process()


def _verify():
    challenge = frappe.form_dict.get("hub.challenge")
    verify_token = frappe.form_dict.get("hub.verify_token")

    matched = frappe.db.get_value(
        "DL WhatsApp Account",
        {"webhook_verify_token": verify_token},
        "name",
    )
    if not matched:
        frappe.throw("Invalid verify token")
    return Response(challenge, status=200)


def _process():
    data = frappe.local.form_dict
    write_log("Incoming Webhook", data)

    try:
        entry = data.get("entry", [{}])[0]
        change = entry.get("changes", [{}])[0]
        value = change.get("value", {})

        phone_id = value.get("metadata", {}).get("phone_number_id")
        account = get_account_by_phone_id(phone_id) if phone_id else get_default_account()
        if not account:
            frappe.log_error("DL WhatsApp Webhook", f"No account found for phone_id={phone_id}")
            return

        messages = value.get("messages", [])
        statuses = value.get("statuses", [])
        contacts_meta = value.get("contacts", [])

        contact_name_map = {
            c.get("wa_id"): c.get("profile", {}).get("name") for c in contacts_meta
        }

        for msg in messages:
            try:
                _handle_message(msg, account, contact_name_map)
            except Exception:
                frappe.log_error("DL WhatsApp Message Error", frappe.get_traceback())

        for status in statuses:
            try:
                _handle_status(status)
            except Exception:
                frappe.log_error("DL WhatsApp Status Error", frappe.get_traceback())

    except Exception:
        frappe.log_error("DL WhatsApp Webhook Error", frappe.get_traceback())


def _handle_message(msg, account, contact_name_map):
    phone = normalize_phone(msg.get("from", ""))
    sender_name = contact_name_map.get(msg.get("from"), None)
    get_or_create_contact(phone, name=sender_name, account=account.name)

    msg_type = msg.get("type", "text")
    message_id = msg.get("id")
    context = msg.get("context", {})
    is_reply = bool(context and "forwarded" not in context)
    reply_to = context.get("id") if is_reply else None

    doc_data = {
        "doctype": "DL WhatsApp Message",
        "type": "Incoming",
        "from": phone,
        "contact": phone,
        "account": account.name,
        "message_id": message_id,
        "content_type": msg_type,
        "is_reply": is_reply,
        "reply_to_message_id": reply_to,
        "status": "received",
    }

    if msg_type == "text":
        doc_data["message"] = msg["text"]["body"]

    elif msg_type == "reaction":
        doc_data["message"] = msg["reaction"]["emoji"]
        doc_data["reply_to_message_id"] = msg["reaction"]["message_id"]

    elif msg_type == "button":
        doc_data["message"] = msg["button"]["text"]

    elif msg_type == "interactive":
        interactive = msg["interactive"]
        itype = interactive.get("type")
        if itype == "button_reply":
            doc_data["message"] = interactive["button_reply"].get("title", "")
        elif itype == "list_reply":
            doc_data["message"] = interactive["list_reply"].get("title", "")

    elif msg_type in ("image", "audio", "video", "document", "sticker"):
        doc_data["message"] = msg.get(msg_type, {}).get("caption", "")
        doc_data["media_mime_type"] = msg.get(msg_type, {}).get("mime_type", "")
        media_id = msg.get(msg_type, {}).get("id")
        if media_id:
            _download_and_attach(doc_data, media_id, account, msg_type)

    elif msg_type == "location":
        loc = msg.get("location", {})
        doc_data["message"] = (
            f"Location: {loc.get('name', '')} "
            f"({loc.get('latitude')}, {loc.get('longitude')})"
        )

    else:
        doc_data["message"] = str(msg.get(msg_type, ""))

    # Pop private media keys before insert (they are not doctype fields)
    media_content = doc_data.pop("_media_content", None)
    media_filename = doc_data.pop("_media_filename", None)

    msg_doc = frappe.get_doc(doc_data).insert(ignore_permissions=True)

    # Attach downloaded media file
    if media_content and media_filename:
        try:
            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": media_filename,
                "content": media_content,
                "attached_to_doctype": "DL WhatsApp Message",
                "attached_to_name": msg_doc.name,
                "attached_to_field": "attach",
                "is_private": 0,
            }).insert(ignore_permissions=True)
            frappe.db.set_value("DL WhatsApp Message", msg_doc.name, "attach", file_doc.file_url)
        except Exception:
            frappe.log_error("DL WhatsApp File Attach Error", frappe.get_traceback())

    # Auto read receipt
    if account.allow_auto_read_receipt and message_id:
        _send_read_receipt(account, message_id)

    frappe.db.commit()


def _download_and_attach(doc_data, media_id, account, msg_type):
    try:
        token = account.get_password("token")
        headers = {"Authorization": f"Bearer {token}"}
        api_base = f"{account.url or 'https://graph.facebook.com'}/{account.version or 'v21.0'}"

        r = requests.get(f"{api_base}/{media_id}", headers=headers, timeout=15)
        if not r.ok:
            return
        media_url = r.json().get("url")
        if not media_url:
            return

        media_r = requests.get(media_url, headers=headers, timeout=30)
        if not media_r.ok:
            return

        mime = doc_data.get("media_mime_type", "application/octet-stream")
        ext = mime.split("/")[-1].split(";")[0]
        fname = f"wa_{frappe.generate_hash(length=8)}.{ext}"

        # Store temporarily; will be saved after doc insert
        doc_data["_media_content"] = media_r.content
        doc_data["_media_filename"] = fname
    except Exception:
        frappe.log_error("DL WhatsApp Media Download Error", frappe.get_traceback())


def _send_read_receipt(account, message_id):
    try:
        from frappe.integrations.utils import make_post_request
        make_post_request(
            account.get_messages_url(),
            headers=account.get_auth_headers(),
            data=json.dumps({
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            }),
        )
    except Exception:
        pass


def _handle_status(status):
    msg_id = status.get("id")
    new_status = status.get("status")
    if not msg_id or not new_status:
        return

    name = frappe.db.get_value("DL WhatsApp Message", {"message_id": msg_id}, "name")
    if name:
        frappe.db.set_value("DL WhatsApp Message", name, "status", new_status)
        frappe.publish_realtime(
            "dl_whatsapp_status",
            {"name": name, "message_id": msg_id, "status": new_status},
            after_commit=True,
        )
