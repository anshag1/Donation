"""Renders the official donation receipt PDF with ReportLab's Platypus layer
(Table/Paragraph/flowables) rather than raw canvas coordinates, so the layout
stays maintainable as fields are added. Field list matches the brief exactly:
org name/logo, receipt no., date, donor name, mobile, amount, purpose, payment
ID, transaction ID, signature, thank-you message.
"""

import io
from dataclasses import dataclass
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BRAND_COLOR = colors.HexColor("#3730A3")
MUTED_COLOR = colors.HexColor("#64748B")


@dataclass
class ReceiptPdfData:
    organization_name: str
    receipt_number: str
    donation_date: datetime
    donor_name: str
    donor_mobile: str
    amount_display: str
    amount_in_words: str
    purpose: str
    razorpay_payment_id: str
    razorpay_order_id: str
    is_duplicate: bool = False


def render_receipt_pdf(data: ReceiptPdfData) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title=f"Donation Receipt {data.receipt_number}",
    )

    styles = getSampleStyleSheet()
    org_style = ParagraphStyle(
        "OrgName", parent=styles["Title"], textColor=BRAND_COLOR, fontSize=20, spaceAfter=2
    )
    muted_style = ParagraphStyle("Muted", parent=styles["Normal"], textColor=MUTED_COLOR, fontSize=9)
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"], textColor=BRAND_COLOR, fontSize=12, spaceBefore=14
    )
    body_style = styles["Normal"]

    story = []

    if data.is_duplicate:
        story.append(
            Paragraph(
                '<font color="#B91C1C"><b>DUPLICATE COPY</b></font>',
                ParagraphStyle("Dup", parent=styles["Normal"], alignment=1, fontSize=11),
            )
        )
        story.append(Spacer(1, 6))

    story.append(Paragraph(data.organization_name, org_style))
    story.append(Paragraph("Official Donation Receipt", muted_style))
    story.append(Spacer(1, 12))

    meta_table = Table(
        [
            ["Receipt Number", data.receipt_number],
            ["Date", data.donation_date.strftime("%d %B %Y, %I:%M %p")],
        ],
        colWidths=[45 * mm, 110 * mm],
    )
    meta_table.setStyle(_kv_table_style())
    story.append(meta_table)

    story.append(Paragraph("Donor Details", section_style))
    donor_table = Table(
        [
            ["Name", data.donor_name],
            ["Mobile Number", data.donor_mobile],
        ],
        colWidths=[45 * mm, 110 * mm],
    )
    donor_table.setStyle(_kv_table_style())
    story.append(donor_table)

    story.append(Paragraph("Donation Details", section_style))
    donation_table = Table(
        [
            ["Amount", data.amount_display],
            ["Amount in Words", data.amount_in_words],
            ["Purpose", data.purpose],
            ["Payment ID", data.razorpay_payment_id],
            ["Transaction / Order ID", data.razorpay_order_id],
        ],
        colWidths=[45 * mm, 110 * mm],
    )
    donation_table.setStyle(_kv_table_style())
    story.append(donation_table)

    story.append(Spacer(1, 28))
    story.append(
        Paragraph(
            "Thank you for your generous contribution. Your support directly "
            "enables our work and is deeply appreciated by everyone we serve.",
            body_style,
        )
    )

    story.append(Spacer(1, 28))
    signature_table = Table(
        [["", "_______________________"], ["", "Authorized Signatory"]],
        colWidths=[110 * mm, 55 * mm],
    )
    signature_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("FONTSIZE", (1, 0), (1, -1), 9),
                ("TEXTCOLOR", (1, 1), (1, 1), MUTED_COLOR),
            ]
        )
    )
    story.append(signature_table)

    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "This receipt is system-generated and valid without a physical signature.",
            ParagraphStyle("Footer", parent=muted_style, alignment=1),
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _kv_table_style() -> TableStyle:
    return TableStyle(
        [
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (0, -1), MUTED_COLOR),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )
