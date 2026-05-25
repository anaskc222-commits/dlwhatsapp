import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.integrations.utils import make_post_request

from dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_account.dl_whatsapp_account import (
    get_default_account,
)
from dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_contact.dl_whatsapp_contact import (
    get_or_create_contact,
    normalize_phone,
)


class DLWhatsAppMessage(Document):
    def before_insert(self):
        if not self.account:
            account = get_default_account()
            if not account:
                frappe.throw(_("No active DL WhatsApp Account found. Please configure one first."))
            self.account = account.name

        # Ensure contact record exists
        phone = self.to if self.type == "Outgoing" else self.get("from")
        if phone:
            contact = get_or_create_contact(normalize_phone(phone), account=self.account)
            if not self.contact:
                self.contact = contact.name

        if self.type == "Outgoing" and not self.message_id:
            self._send()

    def after_insert(self):
        self._update_contact_stats()
        self._realtime_push()

    def on_update(self):
        self._realtime_push()

    def _send(self):
        account = frappe.get_doc("DL WhatsApp Account", self.account)
        data = self._build_payload(account)
        if not data:
            return
        try:
            response = make_post_request(
                account.get_messages_url(),
                headers=account.get_auth_headers(),
                data=json.dumps(data),
            )
            self.message_id = response["messages"][0]["id"]
            self.status = "sent"
            self.sent_at = now_datetime()
        except Exception:
            res = {}
            try:
                res = frappe.flags.integration_request.json().get("error", {})
            except Exception:
                pass
            error_msg = res.get("message", frappe.get_traceback())
            frappe.log_error("DL WhatsApp Send Error", error_msg)
            self.status = "failed"
            frappe.throw(_(f"WhatsApp send failed: {error_msg}"))

    def _build_payload(self, account):
        to = normalize_phone(self.to)
        base = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}

        if self.is_reply and self.reply_to_message_id:
            base["context"] = {"message_id": self.reply_to_message_id}

        ct = self.content_type

        if ct == "text":
            base["type"] = "text"
            base["text"] = {"preview_url": True, "body": self.message or ""}

        elif ct in ("image", "video", "document"):
            base["type"] = ct
            link = self._get_media_link()
            base[ct] = {"link": link, "caption": self.message or ""}
            if ct == "document":
                fname = (self.attach or "").rsplit("/", 1)[-1] or "document"
                base[ct]["filename"] = fname

        elif ct == "audio":
            base["type"] = "audio"
            base["audio"] = {"link": self._get_media_link()}

        elif ct == "sticker":
            base["type"] = "sticker"
            base["sticker"] = {"link": self._get_media_link()}

        elif ct == "reaction":
            base["type"] = "reaction"
            base["reaction"] = {
                "message_id": self.reply_to_message_id or "",
                "emoji": self.message or "",
            }

        elif ct == "template":
            return self._build_template_payload(account)

        else:
            return None

        return base

    def _build_template_payload(self, account):
        if not self.template:
            frappe.throw(_("Template is required for template messages"))
        tpl = frappe.get_doc("DL WhatsApp Template", self.template)
        to = normalize_phone(self.to)
        components = []

        # Header component — supports DOCUMENT, IMAGE, TEXT, VIDEO
        header_type = (tpl.header_type or "").upper()
        if header_type == "DOCUMENT" and self.attach:
            link = _get_public_base_url().rstrip("/") + self.attach \
                if not self.attach.startswith("http") else self.attach
            fname = self.attach.rsplit("/", 1)[-1] or "document.pdf"
            components.append({
                "type": "header",
                "parameters": [{
                    "type": "document",
                    "document": {"link": link, "filename": fname},
                }],
            })
        elif header_type == "IMAGE" and self.attach:
            link = _get_public_base_url().rstrip("/") + self.attach \
                if not self.attach.startswith("http") else self.attach
            components.append({
                "type": "header",
                "parameters": [{"type": "image", "image": {"link": link}}],
            })
        elif header_type == "TEXT" and tpl.header_text:
            components.append({
                "type": "header",
                "parameters": [{"type": "text", "text": tpl.header_text}],
            })

        # Body parameters
        body_params = []
        if self.template_parameters:
            try:
                vals = json.loads(self.template_parameters)
                for v in (vals if isinstance(vals, list) else vals.values()):
                    body_params.append({"type": "text", "text": str(v)})
            except Exception:
                pass
        if body_params:
            components.append({"type": "body", "parameters": body_params})

        return {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": tpl.template_name,
                "language": {"code": tpl.language_code or "en"},
                "components": components,
            },
        }

    def _get_media_link(self):
        if self.attach:
            if self.attach.startswith("http"):
                return self.attach
            base = _get_public_base_url()
            return base.rstrip("/") + self.attach
        return ""

    def _update_contact_stats(self):
        phone = normalize_phone(self.to if self.type == "Outgoing" else (self.get("from") or ""))
        if not phone:
            return
        preview = (self.message or "")[:100]
        updates = {"last_message": preview, "last_message_time": now_datetime()}
        if self.type == "Incoming":
            current = frappe.db.get_value("DL WhatsApp Contact", phone, "unread_count")
            updates["unread_count"] = (int(current) if current else 0) + 1
        if frappe.db.exists("DL WhatsApp Contact", phone):
            frappe.db.set_value("DL WhatsApp Contact", phone, updates)

    def _realtime_push(self):
        phone = normalize_phone(self.to if self.type == "Outgoing" else (self.get("from") or ""))
        frappe.publish_realtime(
            "dl_whatsapp_message",
            {
                "name": self.name,
                "phone": phone,
                "type": self.type,
                "status": self.status,
                "content_type": self.content_type,
                "message": self.message,
                "attach": self.attach,
                "message_id": self.message_id,
                "creation": str(self.creation),
            },
            after_commit=True,
        )

    @frappe.whitelist()
    def mark_as_read(self):
        if self.type != "Incoming":
            return
        account = frappe.get_doc("DL WhatsApp Account", self.account)
        try:
            make_post_request(
                account.get_messages_url(),
                headers=account.get_auth_headers(),
                data=json.dumps({
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": self.message_id,
                }),
            )
        except Exception:
            pass
        self.status = "read"
        self.save(ignore_permissions=True)

        phone = normalize_phone(self.get("from") or "")
        if phone and frappe.db.exists("DL WhatsApp Contact", phone):
            frappe.db.set_value("DL WhatsApp Contact", phone, "unread_count", 0)


def _get_public_base_url():
    """Return the public base URL for media links, from Settings or frappe.utils.get_url()."""
    try:
        url = frappe.db.get_single_value("DL WhatsApp Settings", "public_base_url")
        if url:
            return url.rstrip("/")
    except Exception:
        pass
    return frappe.utils.get_url().rstrip("/")


def on_doctype_update():
    frappe.db.add_index("DL WhatsApp Message", ["contact", "creation"])
    frappe.db.add_index("DL WhatsApp Message", ["message_id"])
