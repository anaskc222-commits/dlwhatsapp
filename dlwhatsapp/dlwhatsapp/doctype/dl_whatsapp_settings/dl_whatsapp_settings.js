frappe.ui.form.on("DL WhatsApp Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: "dlwhatsapp.dlwhatsapp.api.send.test_connection",
				callback(r) {
					if (r.message && r.message.success) {
						frappe.msgprint({ message: __("Connection successful!"), indicator: "green" });
					} else {
						frappe.msgprint({ message: r.message?.error || __("Connection failed"), indicator: "red" });
					}
				},
			});
		});

		frm.add_custom_button(__("Refresh Contact Names"), () => {
			frappe.confirm(
				__("This will update all contacts that show only a phone number as their name, using Customer / Contact / Lead records. Continue?"),
				() => {
					frappe.call({
						method: "dlwhatsapp.dlwhatsapp.doctype.dl_whatsapp_contact.dl_whatsapp_contact.refresh_contact_names",
						freeze: true,
						freeze_message: __("Looking up names..."),
						callback(r) {
							if (r.message) {
								frappe.msgprint({
									message: __("{0} of {1} contacts updated.", [r.message.updated, r.message.total]),
									indicator: "green",
								});
							}
						},
					});
				}
			);
		}, __("Tools"));
	},
});
