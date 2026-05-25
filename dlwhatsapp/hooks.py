app_name = "dlwhatsapp"
app_title = "DL WhatsApp"
app_publisher = "shihab0020"
app_description = "Full-featured WhatsApp integration for Frappe ERPNext"
app_email = "shihab0020@gmail.com"
app_license = "mit"

app_logo_url = "/assets/dlwhatsapp/images/dlwhatsapp-logo.svg"

add_to_apps_screen = [
    {
        "name": "dlwhatsapp",
        "logo": "/assets/dlwhatsapp/images/dlwhatsapp-logo.svg",
        "title": "DL WhatsApp",
        "route": "/desk/dl-whatsapp",
    }
]

# Include CSS and JS in every desk page
app_include_css = "/assets/dlwhatsapp/css/dlwhatsapp.css"
app_include_js = "/assets/dlwhatsapp/js/dlwhatsapp.js"

# Document event hooks — trigger automated notifications on every doctype
_NOTIFY = "dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_notification.dl_whatsapp_notification.trigger_notifications"
_NOTIFY_ASSIGN = "dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_notification.dl_whatsapp_notification.trigger_assignment_notifications"

doc_events = {
    "*": {
        "after_insert": _NOTIFY,
        "on_update": _NOTIFY,
        "on_submit": _NOTIFY,
        "on_cancel": _NOTIFY,
        "on_trash": _NOTIFY,
    },
    "ToDo": {
        "after_insert": _NOTIFY_ASSIGN,
    },
}
