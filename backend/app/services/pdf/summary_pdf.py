"""Event-wise / monthly / yearly summary PDF reports for a treasurer's
board reporting — separate from the per-donation receipt PDF (receipt_pdf.py),
reusing the same visual style for consistency.
"""

import calendar
import io
from dataclasses import dataclass
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BRAND_COLOR = colors.HexColor("#3730A3")
MUTED_COLOR = colors.HexColor("#64748B")


@dataclass
class SummaryPdfData:
    organization_name: str
    report_title: str
    generated_at: datetime
    total_amount_display: str
    total_count: int
    breakdown_headers: list[str]
    breakdown_rows: list[list[str]]


def render_summary_pdf(data: SummaryPdfData) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title=data.report_title,
    )

    styles = getSampleStyleSheet()
    org_style = ParagraphStyle(
        "OrgName", parent=styles["Title"], textColor=BRAND_COLOR, fontSize=18, spaceAfter=2
    )
    muted_style = ParagraphStyle("Muted", parent=styles["Normal"], textColor=MUTED_COLOR, fontSize=9)
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"], textColor=BRAND_COLOR, fontSize=13, spaceBefore=16
    )

    story = [
        Paragraph(data.organization_name, org_style),
        Paragraph(data.report_title, muted_style),
        Paragraph(f"Generated {data.generated_at.strftime('%d %B %Y, %I:%M %p')}", muted_style),
        Spacer(1, 14),
    ]

    totals_table = Table(
        [["Total collected", data.total_amount_display], ["Total donations", str(data.total_count)]],
        colWidths=[60 * mm, 95 * mm],
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), MUTED_COLOR),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ]
        )
    )
    story.append(totals_table)

    if data.breakdown_rows:
        story.append(Paragraph("Breakdown", section_style))
        table_data = [data.breakdown_headers, *data.breakdown_rows]
        col_width = 155 * mm / len(data.breakdown_headers)
        breakdown_table = Table(table_data, colWidths=[col_width] * len(data.breakdown_headers))
        breakdown_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BACKGROUND", (0, 0), (-1, 0), BRAND_COLOR),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ]
            )
        )
        story.append(breakdown_table)

    doc.build(story)
    return buffer.getvalue()


MONTH_NAMES = list(calendar.month_name)  # index 1-12
