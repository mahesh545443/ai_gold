import os
from reportlab.lib.units import cm, mm
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime
from pathlib import Path


class ProposalGeneratorAgent:
    def __init__(self):
        self.output_folder  = "output_folder"
        self.revised_folder = "revised_quotes"
        for folder in [self.output_folder, self.revised_folder]:
            os.makedirs(folder, exist_ok=True)

        # ── Colors — clean/minimal ──
        self.BLACK      = colors.HexColor("#1A1A1A")
        self.DARK_GREY  = colors.HexColor("#444444")
        self.LIGHT_GREY = colors.HexColor("#F5F5F5")
        self.BORDER     = colors.HexColor("#CCCCCC")
        self.WHITE      = colors.white
        self.HDR_BG     = colors.HexColor("#1A1A2E")   # header only
        self.GOLD_LINE  = colors.HexColor("#C9952A")   # accent line only

        # ── Company Details ──
        self.COMPANY_NAME    = "ANALYTICS AVENUE PVT. LTD."
        self.COMPANY_SUB     = "Authorised Gold Bullion Dealer | BIS Hallmark Certified"
        self.COMPANY_GSTIN   = "33AAACS1234F1ZV"
        self.COMPANY_PHONE   = "+91-44-2345-6789"
        self.COMPANY_EMAIL   = "sales@analyticsavenue.com"
        self.COMPANY_ADDRESS = "Nungambakkam, Chennai – 600 034, Tamil Nadu"
        self.COMPANY_BANK    = "HDFC Bank"
        self.COMPANY_ACC     = "5012345678901234"
        self.COMPANY_IFSC    = "HDFC0001234"
        self.COMPANY_BRANCH  = "Nungambakkam, Chennai"
        BASE_DIR = Path(__file__).resolve().parent.parent
        self.LOGO_PATH = BASE_DIR / "assets" / "aard_new_logo.png"

    # ── PUBLIC ────────────────────────────────────────────────

    def generate_quote(self, lead: dict) -> str:
        is_revision = "negotiation_outcome" in lead
        customer    = lead.get("ai_analysis", {}).get("customer_name", "Valued Customer")
        clean_name  = "".join(x for x in customer if x.isalnum())[:12]
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix      = "REVISED" if is_revision else "QUOTE"
        filename    = f"{prefix}_{clean_name}_{timestamp}.pdf"
        folder      = self.revised_folder if is_revision else self.output_folder
        path        = os.path.join(folder, filename)
        self._build_pdf(path, lead, is_revision)
        print(f"   ✅ PDF Generated: {path}")
        return path

    # ── PDF BUILDER ───────────────────────────────────────────

    def _build_pdf(self, path, lead, is_revision):
        doc = SimpleDocTemplate(
            path, pagesize=A4,
            rightMargin=15*mm, leftMargin=15*mm,
            topMargin=12*mm, bottomMargin=15*mm
        )
        styles = getSampleStyleSheet()
        self._register_styles(styles)
        elements = []

        ai      = lead.get("ai_analysis", {})
        pricing = lead.get("pricing_data", {})
        neg     = lead.get("negotiation_outcome", {})

        elements += self._header(is_revision, neg)
        elements.append(Spacer(1, 5*mm))
        elements += self._bill_to(ai, styles)
        elements.append(Spacer(1, 5*mm))
        elements += self._items_table(pricing, neg, is_revision, styles)
        elements.append(Spacer(1, 4*mm))
        elements += self._totals(pricing, neg, is_revision, styles)
        elements.append(Spacer(1, 5*mm))
        elements += self._live_rate_note(pricing, styles)
        elements.append(Spacer(1, 5*mm))
        elements += self._terms(styles)
        elements.append(Spacer(1, 6*mm))
        elements += self._signature(styles)

        doc.build(elements)

    # ── HEADER ────────────────────────────────────────────────

    def _header(self, is_revision, neg):
        elements = []

        try:
            from reportlab.platypus import Image
            logo = Image(self.LOGO_PATH, width=3.5*cm, height=1.2*cm, kind="proportional")
        except Exception:
            logo = Paragraph(f"<b>{self.COMPANY_NAME}</b>",
                             ParagraphStyle("lp", fontName="Helvetica-Bold",
                                            fontSize=11, textColor=self.WHITE))

        company_block = [
            Paragraph(f"<b>{self.COMPANY_NAME}</b>",
                      ParagraphStyle("cn", fontName="Helvetica-Bold", fontSize=11,
                                     textColor=self.WHITE, leading=15)),
            Paragraph(self.COMPANY_SUB,
                      ParagraphStyle("cs", fontName="Helvetica", fontSize=7.5,
                                     textColor=colors.HexColor("#BBBBBB"), leading=11)),
        ]

        right_block = Paragraph(
            f"<font size=8>"
            f"GSTIN: {self.COMPANY_GSTIN}<br/>"
            f"Phone: {self.COMPANY_PHONE}<br/>"
            f"Email: {self.COMPANY_EMAIL}<br/>"
            f"{self.COMPANY_ADDRESS}"
            f"</font>",
            ParagraphStyle("rb", fontName="Helvetica", fontSize=8,
                           textColor=self.WHITE, leading=12, alignment=TA_RIGHT)
        )

        hdr_tbl = Table([[logo, company_block, right_block]],
                        colWidths=[3.5*cm, 8*cm, 6*cm])
        hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.HDR_BG),
            ("PADDING",    (0, 0), (-1, -1), 10),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",      (2, 0), (2,  0),  "RIGHT"),
        ]))
        elements.append(hdr_tbl)

        # Title bar — white, gold underline
        title = "REVISED COMMERCIAL QUOTATION" if is_revision else "COMMERCIAL QUOTATION"
        title_tbl = Table(
            [[Paragraph(title, ParagraphStyle(
                "tt", fontName="Helvetica-Bold", fontSize=11,
                textColor=self.BLACK, alignment=TA_CENTER))]],
            colWidths=[17.5*cm]
        )
        title_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.WHITE),
            ("LINEBELOW",  (0, 0), (-1, -1), 1.5, self.GOLD_LINE),
            ("LINEABOVE",  (0, 0), (-1, -1), 0.5, self.BORDER),
            ("PADDING",    (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_tbl)

        # Revision note — plain grey bar, no color
        if is_revision:
            decision = neg.get("decision", "COUNTER_OFFER")
            disc     = neg.get("discount_percent", 0)
            note = (f"Revised Quotation — Counter Offer | {disc:.2f}% Discount Applied"
                    if decision == "COUNTER_OFFER"
                    else "Revised Quotation — Final Offer | No Further Discount Possible")
            rev_tbl = Table(
                [[Paragraph(note, ParagraphStyle(
                    "rv", fontName="Helvetica-Bold", fontSize=8.5,
                    textColor=self.DARK_GREY, alignment=TA_CENTER))]],
                colWidths=[17.5*cm]
            )
            rev_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), self.LIGHT_GREY),
                ("LINEBELOW",  (0, 0), (-1, -1), 0.5, self.BORDER),
                ("PADDING",    (0, 0), (-1, -1), 6),
            ]))
            elements.append(rev_tbl)

        return elements

    # ── BILL TO ───────────────────────────────────────────────
    # No Priority, TAT, Classification

    def _bill_to(self, ai, styles):
        quote_no = f"AA-{datetime.now().strftime('%Y%m%d%H%M')}"
        date_str = datetime.now().strftime("%d-%b-%Y")
        customer = ai.get("customer_name", "Valued Customer")
        email    = ai.get("sender_email") or "—"

        data = [
            [Paragraph("<b>BILL TO</b>",       styles["CellBold"]),
             "",
             Paragraph("<b>QUOTE DETAILS</b>", styles["CellBold"]),
             ""],
            [Paragraph(f"<b>{customer}</b>",   styles["CellVal"]),
             Paragraph(f"Email: {email}",      styles["CellSm"]),
             Paragraph(f"Quote No: <b>{quote_no}</b>", styles["CellSm"]),
             Paragraph(f"Date: <b>{date_str}</b>",     styles["CellSm"])],
            ["", "",
             Paragraph("Payment: <b>100% Advance</b>", styles["CellSm"]),
             Paragraph("Validity: <b>7 Days</b>",      styles["CellSm"])],
        ]
        tbl = Table(data, colWidths=[4.5*cm, 5*cm, 4.5*cm, 3.5*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (1, 0), self.LIGHT_GREY),
            ("BACKGROUND", (2, 0), (3, 0), self.LIGHT_GREY),
            ("SPAN",       (0, 0), (1, 0)),
            ("SPAN",       (2, 0), (3, 0)),
            ("GRID",       (0, 0), (-1, -1), 0.4, self.BORDER),
            ("PADDING",    (0, 0), (-1, -1), 6),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ]))
        return [tbl]

    # ── ITEMS TABLE ───────────────────────────────────────────

    def _items_table(self, pricing, neg, is_revision, styles):
        items = pricing.get("line_items", [])

        header = [
            Paragraph("<b>No.</b>",         styles["TH"]),
            Paragraph("<b>Description</b>", styles["TH"]),
            Paragraph("<b>Purity</b>",      styles["TH"]),
            Paragraph("<b>Weight (g)</b>",  styles["TH"]),
            Paragraph("<b>Qty</b>",         styles["TH"]),
            Paragraph("<b>Unit Price</b><br/><font size=7>(Pre-GST)</font>", styles["TH"]),
            Paragraph("<b>Amount</b><br/><font size=7>(Pre-GST)</font>",     styles["TH"]),
        ]
        rows = [header]

        for i, item in enumerate(items, 1):
            if item.get("product_name") == "NOT MATCHED":
                rows.append([
                    str(i),
                    Paragraph(f"{item.get('requested_item','—')}<br/>"
                               f"<font size=7 color='red'>Not found in catalogue</font>",
                               styles["TD"]),
                    "—", "—", str(item.get("qty", 1)), "—", "—"
                ])
                continue

            if is_revision and neg:
                ratio    = item.get("selling_price_per_unit", 0) / max(pricing.get("grand_total_pretax", 1), 1)
                new_unit = (neg.get("new_offered_pretax", 0) * ratio) / max(item.get("qty", 1), 1)
                u_para   = Paragraph(
                    f"<strike>₹{item.get('selling_price_per_unit',0):,.2f}</strike>  "
                    f"<b>₹{new_unit:,.2f}</b>", styles["TDR"])
                l_para   = Paragraph(
                    f"<strike>₹{item.get('line_total_pretax',0):,.2f}</strike>  "
                    f"<b>₹{new_unit * item.get('qty',1):,.2f}</b>", styles["TDR"])
            else:
                u_para = Paragraph(f"₹{item.get('selling_price_per_unit',0):,.2f}", styles["TDR"])
                l_para = Paragraph(f"₹{item.get('line_total_pretax',0):,.2f}",      styles["TDR"])

            rows.append([
                str(i),
                Paragraph(
                    f"<b>{item.get('product_name','—')}</b>"
                    f"<br/><font size=7 color='grey'>SKU: {item.get('sku','—')}</font>",
                    styles["TD"]
                ),
                item.get("purity", "—"),
                str(item.get("weight_per_unit_grams", "—")),
                str(item.get("qty", 1)),
                u_para,
                l_para,
            ])

        tbl = Table(rows,
                    colWidths=[1*cm, 5.5*cm, 1.5*cm, 1.8*cm, 1*cm, 3.3*cm, 3.4*cm],
                    repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1,  0), self.HDR_BG),
            ("TEXTCOLOR",     (0, 0), (-1,  0), self.WHITE),
            ("ALIGN",         (0, 0), (-1,  0), "CENTER"),
            ("LINEBELOW",     (0, 0), (-1,  0), 1.5, self.GOLD_LINE),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [self.WHITE, self.LIGHT_GREY]),
            ("ALIGN",         (5, 1), (-1, -1), "RIGHT"),
            ("ALIGN",         (2, 1), ( 4, -1), "CENTER"),
            ("GRID",          (0, 0), (-1, -1), 0.4, self.BORDER),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("PADDING",       (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return [tbl]

    # ── TOTALS ────────────────────────────────────────────────

    def _totals(self, pricing, neg, is_revision, styles):
        if is_revision and neg:
            pretax  = neg.get("new_offered_pretax",  pricing.get("grand_total_pretax",  0))
            cgst    = neg.get("new_offered_cgst",     0)
            sgst    = neg.get("new_offered_sgst",     0)
            invoice = neg.get("new_invoice_total",    pricing.get("grand_total_invoice", 0))
        else:
            pretax  = pricing.get("grand_total_pretax",  0)
            cgst    = pricing.get("grand_total_cgst",    0)
            sgst    = pricing.get("grand_total_sgst",    0)
            invoice = pricing.get("grand_total_invoice", 0)

        rows = [
            ["", "", Paragraph("Sub Total (Pre-GST):",           styles["TotLabel"]),
                     Paragraph(f"₹{pretax:,.2f}",                styles["TotVal"])],
            ["", "", Paragraph("CGST @ 1.5%:",                   styles["TotLabel"]),
                     Paragraph(f"₹{cgst:,.2f}",                  styles["TotVal"])],
            ["", "", Paragraph("SGST @ 1.5%:",                   styles["TotLabel"]),
                     Paragraph(f"₹{sgst:,.2f}",                  styles["TotVal"])],
            ["", "", Paragraph("<b>GRAND TOTAL (Incl. GST):</b>", styles["TotLabelBold"]),
                     Paragraph(f"<b>₹{invoice:,.2f}</b>",         styles["TotValBold"])],
        ]
        tbl = Table(rows, colWidths=[7*cm, 3.5*cm, 4.5*cm, 2.5*cm])
        tbl.setStyle(TableStyle([
            ("ALIGN",      (2, 0), (-1, -1), "RIGHT"),
            ("LINEABOVE",  (2, 0), (-1,  0), 0.5, self.BORDER),
            ("LINEABOVE",  (2, 3), (-1,  3), 1,   self.BLACK),
            ("LINEBELOW",  (2, 3), (-1,  3), 1,   self.BLACK),
            ("BACKGROUND", (2, 3), (-1,  3), self.LIGHT_GREY),
            ("PADDING",    (0, 0), (-1, -1), 5),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ]))
        return [tbl]

    # ── LIVE RATE NOTE ────────────────────────────────────────

    def _live_rate_note(self, pricing, styles):
        live   = pricing.get("live_gold_price_24k_inr", 0)
        src    = pricing.get("price_source", "—")
        usd_oz = pricing.get("gold_usd_per_oz", 0)
        fx     = pricing.get("usd_inr_rate", 0)
        note   = (f"Gold rate used: ₹{live:,.2f}/gram (24K)  |  "
                  f"COMEX: ${usd_oz:,.2f}/oz  |  USD/INR: ₹{fx:.2f}  |  "
                  f"Source: {src}  |  As on {datetime.now().strftime('%d-%b-%Y %H:%M')}")
        tbl = Table([[Paragraph(note, styles["RateNote"])]], colWidths=[17.5*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.LIGHT_GREY),
            ("BOX",        (0, 0), (-1, -1), 0.5, self.BORDER),
            ("PADDING",    (0, 0), (-1, -1), 6),
        ]))
        return [tbl]

    # ── TERMS ─────────────────────────────────────────────────

    def _terms(self, styles):
        elements = []
        elements.append(Paragraph("TERMS & CONDITIONS", styles["SecHdr"]))
        elements.append(Spacer(1, 3*mm))
        terms = [
            ["1.", "Validity: This quotation is valid for 7 days from date of issue."],
            ["2.", "Payment: 100% advance before dispatch. NEFT / RTGS only."],
            ["3.", "GST: CGST @ 1.5% + SGST @ 1.5% = 3% total, as applicable under GST law."],
            ["4.", "Delivery: 3–7 business days after payment confirmation. Insured shipping."],
            ["5.", "Purity: All gold items are BIS Hallmarked (999/916 as applicable)."],
            ["6.", "Price: Subject to MCX gold rate prevailing at time of final dispatch."],
            ["7.", "Warranty: Purity certificate provided with every consignment."],
        ]
        tbl = Table(terms, colWidths=[0.7*cm, 16.8*cm])
        tbl.setStyle(TableStyle([
            ("FONTSIZE",  (0, 0), (-1, -1), 8),
            ("PADDING",   (0, 0), (-1, -1), 3),
            ("VALIGN",    (0, 0), (-1, -1), "TOP"),
            ("TEXTCOLOR", (0, 0), (-1, -1), self.DARK_GREY),
        ]))
        elements.append(tbl)
        return elements

    # ── SIGNATURE ─────────────────────────────────────────────

    def _signature(self, styles):
        data = [[
            Paragraph(
                f"For <b>{self.COMPANY_NAME}</b><br/><br/><br/>"
                f"________________________<br/>"
                f"<font size=8>(Authorised Signatory)</font>",
                styles["SigText"]
            ),
            Paragraph(
                f"<b>Bank Details:</b><br/>"
                f"Bank: {self.COMPANY_BANK}<br/>"
                f"A/C No: {self.COMPANY_ACC}<br/>"
                f"IFSC: {self.COMPANY_IFSC}<br/>"
                f"Branch: {self.COMPANY_BRANCH}",
                styles["SigText"]
            ),
        ]]
        tbl = Table(data, colWidths=[8.75*cm, 8.75*cm])
        tbl.setStyle(TableStyle([
            ("BOX",      (0, 0), (-1, -1), 0.5, self.BORDER),
            ("LINEAFTER",(0, 0), ( 0, -1), 0.5, self.BORDER),
            ("PADDING",  (0, 0), (-1, -1), 10),
            ("VALIGN",   (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        return [tbl]

    # ── STYLES ────────────────────────────────────────────────

    def _register_styles(self, styles):
        defs = [
            ("CellBold",     dict(fontName="Helvetica-Bold",    fontSize=8,   leading=11, textColor=self.BLACK)),
            ("CellVal",      dict(fontName="Helvetica-Bold",    fontSize=9,   leading=12, textColor=self.BLACK)),
            ("CellSm",       dict(fontName="Helvetica",         fontSize=8,   leading=11, textColor=self.DARK_GREY)),
            ("TH",           dict(fontName="Helvetica-Bold",    fontSize=8,   leading=11, textColor=self.WHITE, alignment=TA_CENTER)),
            ("TD",           dict(fontName="Helvetica",         fontSize=8,   leading=11)),
            ("TDR",          dict(fontName="Helvetica",         fontSize=8,   leading=11, alignment=TA_RIGHT)),
            ("TotLabel",     dict(fontName="Helvetica",         fontSize=8,   leading=11, alignment=TA_RIGHT, textColor=self.DARK_GREY)),
            ("TotLabelBold", dict(fontName="Helvetica-Bold",    fontSize=9,   leading=12, alignment=TA_RIGHT, textColor=self.BLACK)),
            ("TotVal",       dict(fontName="Helvetica",         fontSize=8,   leading=11, alignment=TA_RIGHT, textColor=self.DARK_GREY)),
            ("TotValBold",   dict(fontName="Helvetica-Bold",    fontSize=9,   leading=12, alignment=TA_RIGHT, textColor=self.BLACK)),
            ("RateNote",     dict(fontName="Helvetica-Oblique", fontSize=7.5, leading=10, textColor=self.DARK_GREY, alignment=TA_CENTER)),
            ("SecHdr",       dict(fontName="Helvetica-Bold",    fontSize=8.5, leading=12, textColor=self.BLACK)),
            ("SigText",      dict(fontName="Helvetica",         fontSize=8,   leading=13, textColor=self.DARK_GREY)),
        ]
        for name, kwargs in defs:
            styles.add(ParagraphStyle(name=name, parent=styles["Normal"], **kwargs))
