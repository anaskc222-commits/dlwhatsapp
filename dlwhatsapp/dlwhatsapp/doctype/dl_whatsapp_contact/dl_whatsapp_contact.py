import re
import frappe
from frappe.model.document import Document


class DLWhatsAppContact(Document):
    def before_save(self):
        self.phone = normalize_phone(self.phone)
        if _is_phone_like(self.contact_name):
            better_name = _lookup_party_name(self.phone)
            if better_name:
                self.contact_name = better_name


def get_or_create_contact(phone, name=None, account=None):
    phone = normalize_phone(phone)

    existing_name = (
        frappe.db.exists("DL WhatsApp Contact", phone)
        or frappe.db.exists("DL WhatsApp Contact", "+" + phone)
    )
    if existing_name:
        doc = frappe.get_doc("DL WhatsApp Contact", existing_name)
        if doc.name != phone:
            frappe.rename_doc("DL WhatsApp Contact", doc.name, phone)
            doc.name = phone
        # Update name if currently blank or just the phone number
        if not doc.contact_name or doc.contact_name == doc.phone or doc.contact_name == ("+" + phone):
            better_name = name or _lookup_party_name(phone)
            if better_name:
                frappe.db.set_value("DL WhatsApp Contact", phone, "contact_name", better_name)
                doc.contact_name = better_name
        return doc

    # New contact — try to find a name from ERPNext records
    resolved_name = name or _lookup_party_name(phone) or phone
    doc = frappe.get_doc({
        "doctype": "DL WhatsApp Contact",
        "phone": phone,
        "contact_name": resolved_name,
        "account": account,
    }).insert(ignore_permissions=True)
    return doc


def _lookup_party_name(phone):
    """Look up Customer, Lead, or Frappe Contact by phone number and return their name."""
    if not phone:
        return None

    # Build search variants: with and without leading country code for Saudi numbers
    variants = [phone]
    # If starts with 966 and is 12 digits, also try local 05... format
    if phone.startswith("966") and len(phone) == 12:
        variants.append("0" + phone[3:])
    # If starts with 0 and is 10 digits, also try 966... format
    elif phone.startswith("0") and len(phone) == 10:
        variants.append("966" + phone[1:])

    for variant in variants:
        # 1. Customer mobile_no
        name = frappe.db.get_value("Customer", {"mobile_no": variant}, "customer_name")
        if name:
            return name

        # 2. Customer with mobile_no stored with +
        name = frappe.db.get_value("Customer", {"mobile_no": "+" + variant}, "customer_name")
        if name:
            return name

        # 3. Frappe Contact (linked to customers, suppliers, etc.)
        name = frappe.db.get_value("Contact", {"mobile_no": variant, "status": ("!=", "Passive")}, "full_name")
        if name:
            return name
        name = frappe.db.get_value("Contact", {"mobile_no": "+" + variant}, "full_name")
        if name:
            return name
        # Also check phone field on Contact
        name = frappe.db.get_value("Contact", {"phone": variant}, "full_name")
        if name:
            return name

        # 4. Lead
        name = frappe.db.get_value("Lead", {"mobile_no": variant, "status": ("!=", "Do Not Contact")}, "lead_name")
        if name:
            return name

    return None


@frappe.whitelist()
def refresh_contact_names():
    """Backfill names for all contacts that still show only a phone number as their name."""
    contacts = frappe.get_all(
        "DL WhatsApp Contact",
        fields=["name", "phone", "contact_name"],
    )
    updated = 0
    for c in contacts:
        if _is_phone_like(c.contact_name) or not c.contact_name:
            better = _lookup_party_name(c.phone)
            if better:
                frappe.db.set_value("DL WhatsApp Contact", c.name, "contact_name", better)
                updated += 1
    frappe.db.commit()
    return {"updated": updated, "total": len(contacts)}


def _is_phone_like(value):
    """Return True if a contact_name looks like a phone number rather than a real name."""
    if not value:
        return True
    cleaned = re.sub(r"[\s+\-()]", "", value)
    return bool(re.match(r"^\d{7,15}$", cleaned))


def normalize_phone(phone):
    """Normalize to digits-only without leading +, stripping spaces and Unicode marks."""
    phone = str(phone).strip()
    phone = re.sub(r"[​-‏‪-‮⁠﻿]", "", phone)
    if phone.startswith("+"):
        phone = phone[1:]
    return phone.strip()
