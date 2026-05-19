import frappe
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
        version = self.version or "v21.0"
        return f"{url}/{version}"

    def get_messages_url(self):
        return f"{self.get_api_base()}/{self.phone_id}/messages"

    def get_auth_headers(self):
        token = self.get_password("token")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
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
