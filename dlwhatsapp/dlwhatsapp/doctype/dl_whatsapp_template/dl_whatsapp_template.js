frappe.ui.form.on("DL WhatsApp Template", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Sync from Meta"), () => {
				frappe.call({
					method: "dlwhatsapp.dlwhatsapp.api.send.sync_templates",
					freeze: true,
					callback(r) {
						if (r.message) {
							frappe.msgprint({ message: __("Templates synced successfully"), indicator: "green" });
						}
					},
				});
			});
		}
	},
});
