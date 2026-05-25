import json
import requests
import frappe
from frappe import _
from frappe.model.document import Document


class DLWhatsAppAccount(Document):
    def validate(self):
        if self.is_default:
            frappe.db.set_value(
                "DL WhatsApp Account",
                {"name": ("!=", self.name), "is_default": 1},
                "is_default",
                0,
            )

    def get_api_base(self):
        url = self.url or "https://graph.facebook.com"
        version = self.version or "v25.0"
        return f"{url}/{version}"

    def get_messages_url(self):
        return f"{self.get_api_base()}/{self.phone_id}/messages"

    def get_auth_headers(self):
        token = self.get_password("token")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @frappe.whitelist()
    def register_phone(self, pin):
        """Register a Pending phone number for WhatsApp Cloud API messaging.

        pin — a 6-digit code YOU choose; becomes the two-step verification PIN
              for this number. Store it safely — needed for future re-registration.
        """
        if not self.phone_id:
            frappe.throw(_("Phone Number ID is required. Set it from Meta Business Manager → WhatsApp → Phone Numbers."))
        if not pin or not str(pin).isdigit() or len(str(pin)) != 6:
            frappe.throw(_("PIN must be exactly 6 digits."))

        url = f"{self.get_api_base()}/{self.phone_id}/register"
        resp = requests.post(
            url,
            headers=self.get_auth_headers(),
            data=json.dumps({"messaging_product": "whatsapp", "pin": str(pin)}),
            timeout=15,
        )
        result = resp.json()
        if not resp.ok:
            error = result.get("error", {})
            err_msg = error.get("message", resp.text)
            err_code = error.get("code", "")
            err_details = error.get("error_data", {}).get("details", "")
            # Code 100 "Invalid parameter" on an already-registered number usually means wrong PIN
            if err_code == 100 and self.status == "Active":
                frappe.throw(_(
                    "Re-registration failed: the PIN you entered does not match the current "
                    "2-Step Verification PIN for this number. "
                    "Use the same PIN you set during initial registration. "
                    "If you forgot the PIN, disable 2-Step Verification in Meta Business Manager first."
                ))
            frappe.throw(_(f"Registration failed (code {err_code}): {err_msg}. {err_details}").strip(". "))

        self.status = "Active"
        self.save(ignore_permissions=True)
        return {
            "success": True,
            "message": _("Phone number registered successfully! Account is now Active. Save your PIN ({0}) — you will need it if you ever re-register this number.").format(pin),
        }


def get_default_account():
    name = frappe.db.get_value("DL WhatsApp Account", {"is_default": 1, "status": "Active"}, "name")
    if not name:
        name = frappe.db.get_value("DL WhatsApp Account", {"status": "Active"}, "name")
    if name:
        return frappe.get_doc("DL WhatsApp Account", name)
    return None


def get_account_by_phone_id(phone_id):
    name = frappe.db.get_value("DL WhatsApp Account", {"phone_id": phone_id}, "name")
    if name:
        return frappe.get_doc("DL WhatsApp Account", name)
    return None
