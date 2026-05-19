frappe.ui.form.on("DL WhatsApp Account", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Open Chat"), () => {
				frappe.set_route("dlwhatsapp-chat");
			});
			frm.add_custom_button(__("Test Connection"), () => {
				frappe.call({
					method: "dlwhatsapp.dlwhatsapp.api.send.test_connection",
					args: { account: frm.doc.name },
					callback(r) {
						if (r.message && r.message.success) {
							frappe.msgprint({ message: __("Connection successful! Token is valid."), indicator: "green" });
						} else {
							frappe.msgprint({
								title: __("Connection Failed"),
								message: (r.message?.error || __("Connection failed")) +
									"<br><br><b>" + __("If you see an Authentication Error, your Meta API token has expired. Please generate a new token from your Meta Developer App and update it here.") + "</b>",
								indicator: "red",
							});
						}
					},
				});
			});

			const webhookPath = "/api/method/dlwhatsapp.dlwhatsapp.api.webhook.handle";
			const localUrl = `${window.location.origin}${webhookPath}`;
			const publicNote = frm.doc.webhook_verify_token
				? __("Verify Token is set.")
				: __("<b>⚠ Webhook Verify Token is not set.</b> Add a secret string to this field and use it in Meta webhook settings.");

			frm.set_intro(
				__("Webhook URL: <b>{0}</b><br>This URL must be publicly reachable from the internet. If your server is on a local network, use a domain or public IP.<br>Meta Webhook Verify Token field: enter any secret string and use the same in Meta App → Webhook settings.<br>{1}", [localUrl, publicNote]),
				frm.doc.webhook_verify_token ? "blue" : "orange"
			);
		}
	},
});
