frappe.ui.form.on("DL WhatsApp Contact", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Open Chat"), () => {
				frappe.set_route("dlwhatsapp-chat", frm.doc.phone);
			}, __("Action"));

			frm.add_custom_button(__("Send Message"), () => {
				dlwhatsapp.open_send_dialog(frm.doc.phone, frm.doc.contact_name);
			}, __("Action"));
		}
	},
});
