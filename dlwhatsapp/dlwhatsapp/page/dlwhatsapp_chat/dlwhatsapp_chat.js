frappe.pages["dlwhatsapp-chat"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("DL WhatsApp"),
		single_column: true,
	});
	frappe.dlwhatsapp_chat = new DLWhatsAppChatPage(wrapper, page);
};

frappe.pages["dlwhatsapp-chat"].on_page_show = function (wrapper) {
	if (frappe.dlwhatsapp_chat) {
		const route = frappe.get_route();
		if (route[1]) {
			frappe.dlwhatsapp_chat.open_contact(route[1]);
		}
	}
};

class DLWhatsAppChatPage {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.page = page;
		this.current_contact = null;
		this.all_loaded = false;

		this._render_layout();
		this._bind_realtime();
		this._load_contacts();
	}

	_render_layout() {
		// page.body is the correct content area in Frappe 16 (.layout-main-section)
		$(this.page.body).css({ padding: "0", overflow: "hidden" });

		this.$app = $(`
		<div class="dlwa-app">
			<div class="dlwa-sidebar">
				<div class="dlwa-sidebar-header">
					<div class="dlwa-sidebar-title">
						<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="26" height="26">
							<path d="M12 2C6.48 2 2 6.48 2 12C2 13.85 2.51 15.58 3.38 17.07L2 22L7.03 20.64C8.5 21.49 10.19 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM17.5 15.56C17.26 16.22 16.1 16.78 15.54 16.84C14.98 16.9 14.45 17.11 11.72 16.01C8.43 14.71 6.39 11.38 6.24 11.18C6.09 10.98 5 9.55 5 8.07C5 6.59 5.8 5.86 6.08 5.56C6.36 5.26 6.71 5.2 6.93 5.2C7.15 5.2 7.37 5.2 7.56 5.21C7.76 5.22 8.04 5.14 8.31 5.76C8.59 6.39 9.25 7.87 9.33 8.03C9.41 8.19 9.46 8.38 9.36 8.58C9.26 8.78 9.21 8.91 9.06 9.08C8.9 9.26 8.73 9.48 8.59 9.62C8.44 9.77 8.28 9.93 8.45 10.22C8.62 10.51 9.25 11.53 10.17 12.35C11.37 13.42 12.38 13.75 12.67 13.9C12.96 14.05 13.13 14.02 13.3 13.83C13.47 13.64 14.08 12.93 14.27 12.64C14.46 12.35 14.65 12.39 14.91 12.49C15.17 12.59 16.65 13.32 16.93 13.47C17.21 13.62 17.4 13.69 17.48 13.81C17.56 13.93 17.56 14.59 17.5 15.56Z" fill="#25D366"/>
						</svg>
						<span>DL WhatsApp</span>
					</div>
					<div class="dlwa-sidebar-actions">
						<button class="dlwa-icon-btn dlwa-new-chat-btn" title="${__("New Chat")}">
							<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12zM12 6c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3zm-6 8c.67-1.21 1.99-2 3.5-2h5c1.51 0 2.83.79 3.5 2H6z"/></svg>
						</button>
					</div>
				</div>
				<div class="dlwa-search-box">
					<input type="text" class="dlwa-search-input" placeholder="${__("Search contacts")}" />
				</div>
				<div class="dlwa-contact-list"></div>
			</div>

			<div class="dlwa-chat-area dlwa-empty-state">
				<div class="dlwa-empty-content">
					<svg viewBox="0 0 220 188" width="220" xmlns="http://www.w3.org/2000/svg">
						<circle cx="110" cy="94" r="80" fill="#25D366" opacity="0.08"/>
						<path d="M110 40C72.4 40 42 70.4 42 108c0 12.2 3.3 23.7 9.1 33.5L42 162l21.2-5.5C72.5 161.8 81 164 110 164c37.6 0 68-30.4 68-68S147.6 40 110 40z" fill="#25D366" opacity="0.2"/>
					</svg>
					<h3 style="margin-top:16px;color:var(--heading-color)">${__("DL WhatsApp")}</h3>
					<p style="color:var(--text-muted)">${__("Select a contact to start messaging")}</p>
				</div>
			</div>
		</div>`).appendTo(this.page.body);

		this.$contacts = this.$app.find(".dlwa-contact-list");
		this.$chat = this.$app.find(".dlwa-chat-area");
		this.$search = this.$app.find(".dlwa-search-input");

		this.$app.find(".dlwa-new-chat-btn").on("click", () => this._open_new_chat_dialog());
		this.$search.on("input", frappe.utils.debounce(() => this._load_contacts(this.$search.val()), 300));
	}

	_load_contacts(search = "") {
		frappe.call({
			method: "dlwhatsapp.dlwhatsapp.api.send.get_contacts",
			args: { search, limit: 60 },
			callback: (r) => {
				this.$contacts.empty();
				if (!r.message || !r.message.length) {
					this.$contacts.html(`<div class="dlwa-no-contacts">${__("No contacts yet")}</div>`);
					return;
				}
				r.message.forEach((c) => this._render_contact_item(c));
			},
		});
	}

	_render_contact_item(contact) {
		const initials = (contact.contact_name || contact.phone || "?")
			.trim()
			.split(/\s+/)
			.map((w) => w[0])
			.slice(0, 2)
			.join("")
			.toUpperCase();

		const avatar = contact.profile_picture
			? `<img src="${contact.profile_picture}" alt="">`
			: `<span class="dlwa-avatar-initials">${frappe.utils.escape_html(initials)}</span>`;

		const time = contact.last_message_time ? frappe.datetime.prettyDate(contact.last_message_time) : "";
		const preview = frappe.utils.escape_html((contact.last_message || "").substring(0, 48));
		const unread =
			contact.unread_count > 0
				? `<span class="dlwa-unread-badge">${contact.unread_count}</span>`
				: "";
		const isActive = this.current_contact === contact.phone ? "dlwa-active" : "";

		const $item = $(`
		<div class="dlwa-contact-item ${isActive}" data-phone="${frappe.utils.escape_html(contact.phone)}">
			<div class="dlwa-avatar">${avatar}</div>
			<div class="dlwa-contact-info">
				<div class="dlwa-contact-row">
					<span class="dlwa-contact-name">${frappe.utils.escape_html(contact.contact_name || contact.phone)}</span>
					<span class="dlwa-contact-time">${time}</span>
				</div>
				<div class="dlwa-contact-row">
					<span class="dlwa-contact-preview">${preview}</span>
					${unread}
				</div>
			</div>
		</div>`);

		$item.on("click", () => this.open_contact(contact.phone));
		this.$contacts.append($item);
	}

	open_contact(phone) {
		this.current_contact = phone;
		this.all_loaded = false;

		this.$contacts.find(".dlwa-contact-item").removeClass("dlwa-active");
		this.$contacts.find(`.dlwa-contact-item[data-phone="${phone}"]`).addClass("dlwa-active");

		// Render header immediately with phone only so $messages is set before _load_messages runs
		this._render_chat_header({ phone });
		this._load_messages(phone);

		// Update header with full contact info when it arrives
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "DL WhatsApp Contact",
				filters: { phone },
				fieldname: ["phone", "contact_name", "profile_picture"],
			},
			callback: (r) => {
				if (r.message && this.current_contact === phone) {
					this._update_chat_header(r.message);
				}
			},
		});

		frappe.call({ method: "dlwhatsapp.dlwhatsapp.api.send.mark_contact_read", args: { contact: phone } });
	}

	_update_chat_header(contact) {
		const name = contact.contact_name || contact.phone;
		const initials = name.trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
		const avatar = contact.profile_picture
			? `<img src="${contact.profile_picture}" alt="">`
			: `<span class="dlwa-avatar-initials">${initials}</span>`;
		this.$chat.find(".dlwa-chat-contact-name").text(name);
		this.$chat.find(".dlwa-avatar.dlwa-avatar-sm").html(avatar);
	}

	_render_chat_header(contact) {
		const name = contact.contact_name || contact.phone;
		const initials = name
			.trim()
			.split(/\s+/)
			.map((w) => w[0])
			.slice(0, 2)
			.join("")
			.toUpperCase();
		const avatar = contact.profile_picture
			? `<img src="${contact.profile_picture}" alt="">`
			: `<span class="dlwa-avatar-initials">${initials}</span>`;

		this.$chat.removeClass("dlwa-empty-state").html(`
		<div class="dlwa-chat-header">
			<div class="dlwa-avatar dlwa-avatar-sm">${avatar}</div>
			<div class="dlwa-chat-contact-info">
				<div class="dlwa-chat-contact-name">${frappe.utils.escape_html(name)}</div>
				<div class="dlwa-chat-contact-phone">${frappe.utils.escape_html(contact.phone)}</div>
			</div>
			<div class="dlwa-chat-header-actions">
				<button class="dlwa-icon-btn dlwa-send-doc-btn" title="${__("Send Document PDF")}">
					<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-5 11H9v-2h6v2zm3-4H9V7h9v2zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6z"/></svg>
				</button>
				<button class="dlwa-icon-btn dlwa-open-contact-btn" title="${__("Contact Info")}">
					<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
				</button>
			</div>
		</div>
		<div class="dlwa-messages-container">
			<div class="dlwa-load-more" style="display:none">${__("Load older messages")}</div>
			<div class="dlwa-messages-list"></div>
		</div>
		<div class="dlwa-input-area">
			<button class="dlwa-icon-btn dlwa-attach-btn" title="${__("Attach file")}">
				<svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5S15 16.88 15 15.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/></svg>
			</button>
			<textarea class="dlwa-message-input" rows="1" placeholder="${__("Type a message")}"></textarea>
			<button class="dlwa-icon-btn dlwa-template-btn" title="${__("Send Template")}">
				<svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M14 2H6C4.9 2 4 2.9 4 4v16c0 1.1.89 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM6 20V4h5v7h7v9H6z"/></svg>
			</button>
			<button class="dlwa-send-btn">
				<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
			</button>
			<input type="file" class="dlwa-file-input" style="display:none"
				accept="image/*,video/*,audio/*,application/pdf,.doc,.docx,.xls,.xlsx">
		</div>`);

		this.$messages = this.$chat.find(".dlwa-messages-list");
		this.$input = this.$chat.find(".dlwa-message-input");
		this.$load_more = this.$chat.find(".dlwa-load-more");

		this.$chat.find(".dlwa-send-btn").on("click", () => this._send_message());
		this.$input.on("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				this._send_message();
			}
		});
		this.$input.on("input", function () {
			this.style.height = "auto";
			this.style.height = Math.min(this.scrollHeight, 120) + "px";
		});
		this.$chat.find(".dlwa-attach-btn").on("click", () => this.$chat.find(".dlwa-file-input").click());
		this.$chat.find(".dlwa-file-input").on("change", (e) => this._handle_file_upload(e));
		this.$chat.find(".dlwa-template-btn").on("click", () => this._open_template_dialog());
		this.$chat.find(".dlwa-send-doc-btn").on("click", () => this._open_send_doc_dialog());
		this.$chat.find(".dlwa-open-contact-btn").on("click", () => {
			frappe.set_route("Form", "DL WhatsApp Contact", contact.phone);
		});
		this.$load_more.on("click", () => this._load_older_messages());
	}

	_load_messages(phone) {
		frappe.call({
			method: "dlwhatsapp.dlwhatsapp.api.send.get_messages",
			args: { contact: phone, limit: 50 },
			callback: (r) => {
				if (!this.$messages || this.current_contact !== phone) return;
				this.$messages.empty();
				const msgs = r.message || [];
				if (msgs.length >= 50) this.$load_more.show();
				msgs.forEach((m) => this._render_message(m));
				this._scroll_bottom();
			},
		});
	}

	_load_older_messages() {
		if (this.all_loaded) return;
		const first = this.$messages.find(".dlwa-msg-wrap").first();
		const before = first.data("creation");
		if (!before) return;

		frappe.call({
			method: "dlwhatsapp.dlwhatsapp.api.send.get_messages",
			args: { contact: this.current_contact, limit: 40, before },
			callback: (r) => {
				const msgs = r.message || [];
				if (msgs.length < 40) {
					this.all_loaded = true;
					this.$load_more.hide();
				}
				const container = this.$chat.find(".dlwa-messages-container")[0];
				const prev_height = container.scrollHeight;
				msgs.reverse().forEach((m) => this.$messages.prepend(this._build_message_el(m)));
				container.scrollTop = container.scrollHeight - prev_height;
			},
		});
	}

	_render_message(msg) {
		if (!this.$messages) return;
		if (this.$messages.find(`[data-name="${msg.name}"]`).length) return;
		this.$messages.append(this._build_message_el(msg));
	}

	_build_message_el(msg) {
		const outgoing = msg.type === "Outgoing";
		const side = outgoing ? "dlwa-outgoing" : "dlwa-incoming";
		const time = msg.creation ? frappe.datetime.str_to_user(msg.creation) : "";
		const status = outgoing ? this._status_icon(msg.status) : "";

		let body = "";
		const ct = msg.content_type || "text";

		if (ct === "image" && msg.attach) {
			body = `<img class="dlwa-msg-image" src="${msg.attach}" loading="lazy">
				<p class="dlwa-msg-caption">${frappe.utils.escape_html(msg.message || "")}</p>`;
		} else if (ct === "video" && msg.attach) {
			body = `<video class="dlwa-msg-video" controls src="${msg.attach}"></video>`;
		} else if (ct === "audio" && msg.attach) {
			body = `<audio controls class="dlwa-msg-audio"><source src="${msg.attach}"></audio>`;
		} else if (ct === "document" && msg.attach) {
			const fname = msg.attach.split("/").pop();
			body = `<a class="dlwa-msg-doc" href="${msg.attach}" target="_blank" download>
				<svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M14 2H6C4.9 2 4 2.9 4 4v16c0 1.1.89 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM6 20V4h5v7h7v9H6z"/></svg>
				<span>${frappe.utils.escape_html(msg.message || fname)}</span>
			</a>`;
		} else if (ct === "sticker" && msg.attach) {
			body = `<img class="dlwa-msg-sticker" src="${msg.attach}">`;
		} else if (ct === "reaction") {
			body = `<p class="dlwa-msg-emoji">${frappe.utils.escape_html(msg.message || "")}</p>`;
		} else {
			const text = this._linkify(frappe.utils.escape_html(msg.message || ""));
			body = `<p class="dlwa-msg-text">${text}</p>`;
		}

		return $(`
		<div class="dlwa-msg-wrap ${side}" data-name="${msg.name}" data-creation="${msg.creation}">
			<div class="dlwa-msg-bubble">
				${body}
				<div class="dlwa-msg-meta">
					<span class="dlwa-msg-time">${time}</span>
					${status}
				</div>
			</div>
		</div>`);
	}

	_status_icon(status) {
		const map = {
			sent: `<span class="dlwa-tick dlwa-tick-sent" title="${__("Sent")}">✓</span>`,
			delivered: `<span class="dlwa-tick dlwa-tick-delivered" title="${__("Delivered")}">✓✓</span>`,
			read: `<span class="dlwa-tick dlwa-tick-read" title="${__("Read")}">✓✓</span>`,
			failed: `<span class="dlwa-tick dlwa-tick-failed" title="${__("Failed")}">✗</span>`,
		};
		return map[status] || "";
	}

	_linkify(text) {
		return text.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank">$1</a>');
	}

	_send_message() {
		const msg = (this.$input.val() || "").trim();
		if (!msg || !this.current_contact) return;
		this.$input.val("").css("height", "auto");

		frappe.call({
			method: "dlwhatsapp.dlwhatsapp.api.send.send_message",
			args: { to: this.current_contact, message: msg, content_type: "text" },
			callback: (r) => {
				if (r.message) this._load_messages(this.current_contact);
			},
		});
	}

	_handle_file_upload(e) {
		const file = e.target.files[0];
		if (!file || !this.current_contact) return;

		const reader = new FileReader();
		reader.onload = (ev) => {
			const content = ev.target.result.split(",")[1];
			frappe.call({
				method: "frappe.client.save",
				args: { doc: { doctype: "File", file_name: file.name, content, decode: true, is_private: 0 } },
				callback: (r) => {
					if (!r.message) return;
					const url = r.message.file_url;
					const mime = file.type;
					let ct = "document";
					if (mime.startsWith("image/")) ct = "image";
					else if (mime.startsWith("video/")) ct = "video";
					else if (mime.startsWith("audio/")) ct = "audio";

					frappe.call({
						method: "dlwhatsapp.dlwhatsapp.api.send.send_message",
						args: { to: this.current_contact, message: file.name, content_type: ct, attach: url },
						callback: () => this._load_messages(this.current_contact),
					});
				},
			});
		};
		reader.readAsDataURL(file);
		e.target.value = "";
	}

	_open_template_dialog() {
		frappe.call({
			method: "dlwhatsapp.dlwhatsapp.api.send.get_templates",
			callback: (r) => {
				const templates = r.message || [];
				if (!templates.length) {
					frappe.msgprint(__("No approved templates. Go to DL WhatsApp Template and sync from Meta."));
					return;
				}
				const d = new frappe.ui.Dialog({
					title: __("Send Template"),
					fields: [
						{
							fieldname: "template",
							label: __("Select Template"),
							fieldtype: "Select",
							options: templates.map((t) => t.name),
							reqd: 1,
						},
					],
					primary_action_label: __("Send"),
					primary_action: (vals) => {
						frappe.call({
							method: "dlwhatsapp.dlwhatsapp.api.send.send_template",
							args: { to: this.current_contact, template: vals.template },
							callback: () => this._load_messages(this.current_contact),
						});
						d.hide();
					},
				});
				d.show();
			},
		});
	}

	_open_send_doc_dialog() {
		const d = new frappe.ui.Dialog({
			title: __("Send Document as PDF"),
			fields: [
				{
					fieldname: "doctype",
					label: __("DocType"),
					fieldtype: "Link",
					options: "DocType",
					reqd: 1,
					onchange() {
						const dt = d.get_value("doctype");
						if (!dt) return;
						// Auto-fill print format and caption from Settings
						frappe.call({
							method: "dlwhatsapp.dlwhatsapp.api.send.get_pdf_print_format",
							args: { doctype: dt },
							callback(r) {
								const fmt = r.message || {};
								if (fmt.print_format) d.set_value("print_format", fmt.print_format);
								if (fmt.caption) d.set_value("caption", fmt.caption);
							},
						});
					},
				},
				{
					fieldname: "docname",
					label: __("Document"),
					fieldtype: "Dynamic Link",
					options: "doctype",
					reqd: 1,
					get_query() {
						return { doctype: d.get_value("doctype") };
					},
				},
				{
					fieldname: "print_format",
					label: __("Print Format"),
					fieldtype: "Link",
					options: "Print Format",
					get_query() {
						return { filters: { doc_type: d.get_value("doctype") } };
					},
				},
				{
					fieldname: "caption",
					label: __("Caption"),
					fieldtype: "Data",
					description: __("Message sent with the PDF. Defaults to document name."),
				},
			],
			primary_action_label: __("Send PDF"),
			primary_action: (vals) => {
				frappe.call({
					method: "dlwhatsapp.dlwhatsapp.api.send.send_document_pdf",
					args: {
						to: this.current_contact,
						doctype: vals.doctype,
						docname: vals.docname,
						print_format: vals.print_format,
					},
					freeze: true,
					freeze_message: __("Generating and sending PDF…"),
					callback: (r) => {
						if (r.message) {
							frappe.show_alert({ message: __("PDF sent!"), indicator: "green" });
							this._load_messages(this.current_contact);
						}
					},
				});
				d.hide();
			},
		});
		d.show();
	}

	_open_new_chat_dialog() {
		const d = new frappe.ui.Dialog({
			title: __("New Chat"),
			fields: [
				{ fieldname: "phone", label: __("Phone Number"), fieldtype: "Data", reqd: 1,
				  description: __("Include country code, e.g. +966512345678") },
				{ fieldname: "name_", label: __("Contact Name"), fieldtype: "Data" },
			],
			primary_action_label: __("Start Chat"),
			primary_action: (vals) => {
				const phone = (vals.phone || "").replace(/\D/g, "");
				if (!phone) return;
				frappe.call({
					method: "dlwhatsapp.dlwhatsapp.api.send.ensure_contact",
					args: { phone, contact_name: vals.name_ || phone },
					callback: () => {
						this._load_contacts();
						setTimeout(() => this.open_contact(phone), 400);
					},
				});
				d.hide();
			},
		});
		d.show();
	}

	_scroll_bottom() {
		const c = this.$chat.find(".dlwa-messages-container")[0];
		if (c) c.scrollTop = c.scrollHeight;
	}

	_bind_realtime() {
		frappe.realtime.on("dl_whatsapp_message", (data) => {
			if (!this.current_contact) return;
			const phone = (data.phone || "").replace(/^\+/, "");
			const cur = (this.current_contact || "").replace(/^\+/, "");
			if (phone === cur) {
				this._render_message({
					name: data.name,
					type: data.type,
					status: data.status,
					content_type: data.content_type,
					message: data.message,
					attach: data.attach,
					creation: data.creation,
				});
				this._scroll_bottom();
				if (data.type === "Incoming") {
					frappe.call({ method: "dlwhatsapp.dlwhatsapp.api.send.mark_contact_read", args: { contact: cur } });
				}
			}
			this._load_contacts(this.$search.val());
		});

		frappe.realtime.on("dl_whatsapp_status", (data) => {
			if (!this.$messages) return;
			this.$messages
				.find(`[data-name="${data.name}"] .dlwa-tick`)
				.replaceWith(this._status_icon(data.status));
		});
	}
}

// Global helper used from form buttons
window.dlwhatsapp = window.dlwhatsapp || {};
dlwhatsapp.open_send_dialog = function (phone, contact_name) {
	frappe.call({
		method: "dlwhatsapp.dlwhatsapp.api.send.get_templates",
		callback(r) {
			const templates = r.message || [];
			const d = new frappe.ui.Dialog({
				title: __("Send WhatsApp Message"),
				fields: [
					{ fieldname: "phone", label: __("Phone"), fieldtype: "Data", default: phone || "", reqd: 1 },
					{
						fieldname: "message_type",
						label: __("Type"),
						fieldtype: "Select",
						options: templates.length ? "Text\nTemplate" : "Text",
						default: "Text",
					},
					{ fieldname: "message", label: __("Message"), fieldtype: "Text",
					  depends_on: 'eval:doc.message_type=="Text"' },
					{ fieldname: "template", label: __("Template"), fieldtype: "Select",
					  options: templates.map((t) => t.name),
					  depends_on: 'eval:doc.message_type=="Template"' },
				],
				primary_action_label: __("Send"),
				primary_action(vals) {
					const to = (vals.phone || "").replace(/\s/g, "");
					if (vals.message_type === "Template") {
						frappe.call({
							method: "dlwhatsapp.dlwhatsapp.api.send.send_template",
							args: { to, template: vals.template },
							callback() { frappe.show_alert({ message: __("Sent!"), indicator: "green" }); },
						});
					} else {
						frappe.call({
							method: "dlwhatsapp.dlwhatsapp.api.send.send_message",
							args: { to, message: vals.message },
							callback() { frappe.show_alert({ message: __("Sent!"), indicator: "green" }); },
						});
					}
					d.hide();
				},
			});
			d.show();
		},
	});
};
