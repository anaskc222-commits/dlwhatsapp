frappe.ui.form.on("DL WhatsApp Notification", {
	refresh(frm) {},
	document_type(frm) {
		if (frm.doc.document_type) {
			frm.set_query("template", () => ({
				filters: [
					["DL WhatsApp Template", "for_doctype", "in", [frm.doc.document_type, ""]],
				],
			}));
		}
	},
});
