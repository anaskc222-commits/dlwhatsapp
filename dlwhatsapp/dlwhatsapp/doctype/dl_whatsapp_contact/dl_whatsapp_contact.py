import frappe
from frappe.model.document import Document


class DLWhatsAppContact(Document):
    pass


def get_or_create_contact(phone, name=None, account=None):
    phone = normalize_phone(phone)
    if frappe.db.exists("DL WhatsApp Contact", phone):
        doc = frappe.get_doc("DL WhatsApp Contact", phone)
        if name and not doc.contact_name:
            doc.contact_name = name
            doc.save(ignore_permissions=True)
        return doc

    doc = frappe.get_doc({
        "doctype": "DL WhatsApp Contact",
        "phone": phone,
        "contact_name": name or phone,
        "account": account,
    }).insert(ignore_permissions=True)
    return doc


def normalize_phone(phone):
    phone = str(phone).strip()
    if phone.startswith("+"):
        phone = phone[1:]
    return phone
