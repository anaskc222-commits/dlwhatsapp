frappe.ui.form.on("DL WhatsApp Message", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.type === "Incoming" && frm.doc.message_id) {
			frm.add_custom_button(__("Mark as Read"), () => {
				frm.call("mark_as_read").then(() => {
					frappe.show_alert({ message: __("Marked as read"), indicator: "green" });
					frm.reload_doc();
				});
			});
		}
		if (!frm.is_new() && frm.doc.contact) {
			frm.add_custom_button(__("Open Chat"), () => {
				frappe.set_route("dlwhatsapp-chat", frm.doc.contact);
			});
		}
	},
});
