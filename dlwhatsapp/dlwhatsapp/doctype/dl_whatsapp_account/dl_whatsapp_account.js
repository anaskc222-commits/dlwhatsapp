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
			}, __("Phone Registration"));

			frm.add_custom_button(__("Register Phone Number"), () => {
				const already_active = frm.doc.status === "Active";
				const d = new frappe.ui.Dialog({
					title: already_active
						? __("Re-register / Update PIN")
						: __("Register Phone Number for WhatsApp"),
					fields: [
						{
							fieldname: "info",
							fieldtype: "HTML",
							options: already_active
								? `<div class="alert alert-info" style="margin-bottom:12px">
									<b>ℹ️ ${__("This number is already registered with WhatsApp Cloud API.")}</b><br><br>
									${__("To re-register or update your PIN, enter your <b>current 2-Step Verification PIN</b> (the 6-digit PIN you set during initial registration).")}
									<br><br>
									<b>${__("⚠️ Using the wrong PIN will fail. If you forgot your PIN, you must disable 2-Step Verification in Meta Business Manager first.")}</b>
								</div>`
								: `<div class="alert alert-warning" style="margin-bottom:12px">
									<b>📋 ${__("Before you proceed:")}</b>
									<ol style="margin:8px 0 0 16px;padding:0">
										<li>${__("Your phone number must be verified in Meta Business Manager")}</li>
										<li>${__("Your access token must have <b>whatsapp_business_messaging</b> permission")}</li>
										<li>${__("Choose any 6-digit PIN — this becomes your WhatsApp 2-Step Verification PIN. <b>Save it securely.</b>")}</li>
									</ol>
								</div>`,
						},
						{
							fieldname: "pin",
							label: already_active ? __("Current 6-Digit PIN") : __("Set 6-Digit PIN"),
							fieldtype: "Password",
							reqd: 1,
							description: already_active
								? __("Enter the PIN you set when you first registered this number.")
								: __("Choose any 6 digits. This PIN protects your WhatsApp number — save it safely."),
						},
						...(!already_active ? [{
							fieldname: "pin_confirm",
							label: __("Confirm PIN"),
							fieldtype: "Password",
							reqd: 1,
						}] : []),
					],
					primary_action_label: already_active ? __("Re-register") : __("Register"),
					primary_action(vals) {
						if (!already_active && vals.pin !== vals.pin_confirm) {
							frappe.msgprint({ message: __("PINs do not match."), indicator: "red" });
							return;
						}
						if (!/^\d{6}$/.test(vals.pin)) {
							frappe.msgprint({ message: __("PIN must be exactly 6 digits."), indicator: "red" });
							return;
						}
						frm.call({
							doc: frm.doc,
							method: "register_phone",
							args: { pin: vals.pin },
							freeze: true,
							freeze_message: __("Registering phone number with WhatsApp..."),
							callback(r) {
								if (r.message && r.message.success) {
									d.hide();
									frappe.msgprint({
										title: __("Registration Successful! 🎉"),
										message: r.message.message,
										indicator: "green",
									});
									frm.reload_doc();
								}
							},
						});
					},
				});
				d.show();
			}, __("Phone Registration"));

			const webhookPath = "/api/method/dlwhatsapp.dlwhatsapp.api.webhook.handle";
			const localUrl = `${window.location.origin}${webhookPath}`;
			const publicNote = frm.doc.webhook_verify_token
				? __("Verify Token is set.")
				: __("<b>⚠ Webhook Verify Token is not set.</b> Add a secret string to this field and use it in Meta webhook settings.");

			frm.set_intro(
				__("Webhook URL: <b>{0}</b><br>This URL must be publicly reachable from the internet.<br>Meta Webhook Verify Token field: enter any secret string and use the same in Meta App → Webhook settings.<br>{1}", [localUrl, publicNote]),
				frm.doc.webhook_verify_token ? "blue" : "orange"
			);
		}
	},
});
