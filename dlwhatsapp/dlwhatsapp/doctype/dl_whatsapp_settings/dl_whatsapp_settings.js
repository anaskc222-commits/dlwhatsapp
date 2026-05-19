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
	},
});
