/* DL WhatsApp — desk-wide integration */
(function () {
	"use strict";

	// Add "Send WhatsApp" button to every form that has a mobile/phone field
	const PHONE_FIELDS = ["mobile_no", "phone", "contact_mobile", "whatsapp_no", "mobile", "phone_no"];
	const LINKED_DOCTYPE_FIELDS = {
		"Sales Invoice": "contact_mobile",
		"Sales Order": "contact_mobile",
		"Purchase Order": "",
		"Quotation": "contact_mobile",
		"Delivery Note": "contact_mobile",
		"Payment Entry": "",
		"Lead": "mobile_no",
		"Customer": "mobile_no",
		"Supplier": "mobile_no",
	};

	frappe.router.on("change", () => {
		const route = frappe.get_route();
		if (route && route[0] === "Form") {
			frappe.ui.form.on(route[1], {
				refresh(frm) {
					_add_whatsapp_button(frm);
				},
			});
		}
	});

	function _add_whatsapp_button(frm) {
		if (frm.custom_buttons && frm.custom_buttons[__("Send WhatsApp")]) return;

		const phone = _get_phone(frm);
		frm.add_custom_button(
			__("Send WhatsApp"),
			() => {
				const resolved_phone = _get_phone(frm);
				if (!resolved_phone) {
					frappe.msgprint(__("No phone number found on this document."));
					return;
				}
				_show_send_dialog(frm, resolved_phone);
			},
			__("WhatsApp")
		);
	}

	function _get_phone(frm) {
		// 1. Check known field for this doctype
		const known = LINKED_DOCTYPE_FIELDS[frm.doctype];
		if (known && frm.doc[known]) return frm.doc[known];

		// 2. Scan common field names
		for (const f of PHONE_FIELDS) {
			if (frm.doc[f]) return frm.doc[f];
		}

		// 3. Look at all fields
		for (const field of frm.meta.fields || []) {
			if (["Data", "Phone"].includes(field.fieldtype)) {
				const val = frm.doc[field.fieldname];
				if (val && /\d{7,}/.test(String(val))) return val;
			}
		}
		return null;
	}

	function _show_send_dialog(frm, phone) {
		frappe.call({
			method: "dlwhatsapp.dlwhatsapp.api.send.get_pdf_print_format",
			args: { doctype: frm.doctype },
			callback(fmt_r) {
				const default_fmt = (fmt_r.message || {}).print_format || "";

				const d = new frappe.ui.Dialog({
					title: __("Send WhatsApp Message"),
					fields: [
						{
							fieldname: "phone",
							label: __("Phone Number"),
							fieldtype: "Data",
							default: phone,
							reqd: 1,
						},
						{
							fieldname: "message",
							label: __("Message"),
							fieldtype: "Small Text",
							reqd: 0,
						},
						{
							fieldname: "attach_pdf",
							label: __("Attach PDF"),
							fieldtype: "Check",
							default: default_fmt ? 1 : 0,
							description: __("Attach {0} as a PDF document", [frm.doctype]),
						},
						{
							fieldname: "print_format",
							label: __("Print Format"),
							fieldtype: "Link",
							options: "Print Format",
							default: default_fmt,
							depends_on: "eval:doc.attach_pdf == 1",
							get_query() {
								return { filters: { doc_type: frm.doctype } };
							},
						},
					],
					primary_action_label: __("Send"),
					primary_action(vals) {
						const phone_clean = (vals.phone || "").replace(/\s/g, "");
						const has_msg = (vals.message || "").trim();
						const has_pdf = vals.attach_pdf;

						if (!has_msg && !has_pdf) {
							frappe.msgprint(__("Please enter a message or attach a PDF."));
							return;
						}
						d.hide();

						const _done = () => {
							frappe.show_alert({ message: __("Sent via WhatsApp!"), indicator: "green" });
							_add_timeline_comment(frm, has_pdf ? "PDF" : "Text", phone_clean,
								has_msg || frm.docname);
						};

						if (has_pdf) {
							frappe.call({
								method: "dlwhatsapp.dlwhatsapp.api.send.send_document_pdf",
								args: {
									to: phone_clean,
									doctype: frm.doctype,
									docname: frm.docname,
									print_format: vals.print_format,
									caption: has_msg || frm.docname,
								},
								freeze: true,
								freeze_message: __("Generating and sending PDF..."),
								callback: _done,
							});
						} else {
							frappe.call({
								method: "dlwhatsapp.dlwhatsapp.api.send.send_message",
								args: { to: phone_clean, message: has_msg },
								freeze: true,
								callback: _done,
							});
						}
					},
				});
				d.show();
			},
		});
	}

	function _add_timeline_comment(frm, type, phone, content) {
		frappe.call({
			method: "frappe.desk.form.utils.add_comment",
			args: {
				reference_doctype: frm.doctype,
				reference_name: frm.docname,
				content: `<b>WhatsApp ${type}</b> sent to <b>${phone}</b>: ${content}`,
				comment_by: frappe.session.user_fullname,
				comment_email: frappe.session.user,
			},
		});
	}
})();
