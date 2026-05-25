# DL WhatsApp

**Full-featured WhatsApp Business integration for Frappe & ERPNext**

Send quotations, invoices, delivery notes, and custom notifications via WhatsApp directly from your ERPNext desk. Built on the [Meta WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api).

![Frappe](https://img.shields.io/badge/Frappe-16-blue) ![ERPNext](https://img.shields.io/badge/ERPNext-16-orange) ![License](https://img.shields.io/badge/License-MIT-green) ![Meta Cloud API](https://img.shields.io/badge/Meta%20Cloud%20API-v25.0-brightgreen)

---

## ✨ Features

- **WhatsApp Chat Page** — Full in-desk chat UI: send/receive messages, images, documents, audio, templates, and emoji reactions
- **Send PDFs from any document** — Quotation, Sales Invoice, Delivery Note — one click sends a PDF via WhatsApp with a template header
- **Template Messages** — Sync and send approved Meta templates with dynamic fields from any ERPNext document
- **Workflow Notifications** — Automatically notify approvers or roles when a workflow state changes
- **Assignment Notifications** — Notify users when a document is assigned to them
- **Auto Contact Names** — Contacts are automatically named from ERPNext Customer / Contact / Lead records by phone number
- **24-Hour Session Management** — Detects expired sessions, auto-sends a greeting template, and queues the user's message
- **Multi-Account Support** — Multiple WhatsApp Business numbers with a default account
- **Real-time Updates** — Messages and delivery status update live via Frappe's realtime engine
- **Webhook Handling** — Processes incoming messages, media, reactions, and delivery receipts

---

## 📋 Requirements

- Frappe / ERPNext **v16**
- A [Meta Developer App](https://developers.facebook.com/) with WhatsApp product enabled
- A verified WhatsApp Business phone number
- Meta API token with `whatsapp_business_messaging` permission (add `whatsapp_business_management` to sync/create templates)

---

## 🚀 Installation

```bash
cd /path/to/frappe-bench
bench get-app https://github.com/shihab0020/dlwhatsapp --branch main
bench --site your-site install-app dlwhatsapp
bench migrate
```

---

## ⚙️ Setup

1. **DL WhatsApp Account** — Add your Meta Phone Number ID, WABA ID, and API token
2. **Register Phone** — Use the *Register Phone Number* button to activate the Cloud API
3. **Webhook** — Point your Meta App webhook to:
   ```
   https://your-site.com/api/method/dlwhatsapp.dlwhatsapp.api.webhook.handle
   ```
4. **DL WhatsApp Settings** — Enable notifications, set a default welcome template
5. **Sync Templates** — Pull your approved Meta templates into the system

---

## 📬 Sending Messages

### From the Chat Page
Navigate to **DL WhatsApp** → Chat. Select a contact and type freely (within 24h session) or use templates.

### From any ERPNext form
Add a **Send WhatsApp** button to any form using the global helper:
```javascript
dlwhatsapp.open_send_dialog(frm.doc.mobile_no, frm.doc.customer_name);
```

### Send Document as PDF
The *Send Document PDF* button in the chat generates a PDF of any document and sends it — optionally with a template header to bypass the 24h session requirement.

---

## 🔔 Notifications & Workflows

Create rules in **DL WhatsApp Notification** — no code required:

| Event | Description |
|---|---|
| `after_insert` | When a document is created |
| `on_update` | When a document is saved |
| `on_submit` | When a document is submitted |
| `on_workflow_action` | When workflow state changes (filter by state) |
| `on_assign` | When a document is assigned to a user |

**Recipient types:** Phone Field · Static Number · User Field (looks up User mobile_no) · Role (sends to all users with that role)

---

## 📁 Project Structure

```
dlwhatsapp/
├── dlwhatsapp/
│   ├── api/
│   │   ├── send.py          # Whitelisted API endpoints (send, templates, contacts)
│   │   └── webhook.py       # Meta webhook handler
│   ├── doctype/
│   │   ├── dl_whatsapp_account/      # WhatsApp Business account config
│   │   ├── dl_whatsapp_contact/      # Contact management with ERPNext lookup
│   │   ├── dl_whatsapp_message/      # Message send/receive with Meta API
│   │   ├── dl_whatsapp_notification/ # Notification rules engine
│   │   ├── dl_whatsapp_settings/     # Global settings singleton
│   │   └── dl_whatsapp_template/     # Template management & sync
│   └── page/
│       └── dlwhatsapp_chat/          # Full chat page UI
└── public/
    ├── css/dlwhatsapp.css
    └── js/dlwhatsapp.js
```

---

## 📄 License

MIT — see [license.txt](license.txt)

Built by [DLITS](https://dlitsksa.com) — شركة دلتس للحلول التقنية
