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
        "route": "/dlwhatsapp-chat",
    }
]

# Include CSS and JS in every desk page
app_include_css = "/assets/dlwhatsapp/css/dlwhatsapp.css"
app_include_js = "/assets/dlwhatsapp/js/dlwhatsapp.js"

# Document event hooks — trigger automated notifications on every doctype
doc_events = {
    "*": {
        "after_insert": "dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_notification.dl_whatsapp_notification.trigger_notifications",
        "on_update": "dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_notification.dl_whatsapp_notification.trigger_notifications",
        "on_submit": "dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_notification.dl_whatsapp_notification.trigger_notifications",
        "on_cancel": "dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_notification.dl_whatsapp_notification.trigger_notifications",
        "on_trash": "dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_notification.dl_whatsapp_notification.trigger_notifications",
    }
}
