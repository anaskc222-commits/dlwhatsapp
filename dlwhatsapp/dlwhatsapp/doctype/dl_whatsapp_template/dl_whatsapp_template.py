import frappe
from frappe.model.document import Document


class DLWhatsAppTemplate(Document):
    def validate(self):
        self._render_preview()

    def _render_preview(self):
        body = self.body_text or ""
        if self.sample_values:
            vals = [v.strip() for v in self.sample_values.split(",")]
            for i, v in enumerate(vals, 1):
                body = body.replace("{{" + str(i) + "}}", f"<b>{v}</b>")

        header_html = ""
        if self.header_type == "TEXT" and self.header_text:
            header_html = f'<div style="font-weight:bold;margin-bottom:4px">{self.header_text}</div>'

        footer_html = ""
        if self.footer_text:
            footer_html = f'<div style="color:#888;font-size:0.85em;margin-top:4px">{self.footer_text}</div>'

        self.preview_html = f"""
        <div style="background:#dcf8c6;border-radius:8px;padding:12px 16px;max-width:340px;
                    font-family:sans-serif;font-size:14px;line-height:1.4">
            {header_html}
            <div>{body}</div>
            {footer_html}
        </div>
        """
