from datetime import datetime, timezone

from app.services.amount_in_words import amount_in_paise_to_words
from app.services.format_utils import format_inr, format_inr_for_pdf
from app.services.pdf.receipt_pdf import ReceiptPdfData, render_receipt_pdf


def _sample_data(**overrides) -> ReceiptPdfData:
    defaults = dict(
        organization_name="Demo Charitable Trust",
        receipt_number="TEST/2026-27/000001",
        donation_date=datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc),
        donor_name="Jane Donor",
        donor_mobile="9876500000",
        amount_display=format_inr_for_pdf(150000),
        amount_in_words=amount_in_paise_to_words(150000),
        purpose="General Donation",
        razorpay_payment_id="pay_test123",
        razorpay_order_id="order_test123",
    )
    defaults.update(overrides)
    return ReceiptPdfData(**defaults)


def test_render_receipt_pdf_produces_valid_pdf_bytes():
    pdf_bytes = render_receipt_pdf(_sample_data())
    assert pdf_bytes.startswith(b"%PDF-")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")
    assert len(pdf_bytes) > 1000  # a real rendered page, not an empty stub


def test_render_receipt_pdf_duplicate_flag_still_renders():
    pdf_bytes = render_receipt_pdf(_sample_data(is_duplicate=True))
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_format_inr_uses_indian_digit_grouping():
    assert format_inr(150000) == "₹1,500.00"
    assert format_inr(12345600) == "₹1,23,456.00"
    assert format_inr(100) == "₹1.00"


def test_format_inr_for_pdf_avoids_the_unicode_rupee_glyph():
    """Regression test: ReportLab's PDFs use the base-14 Helvetica font,
    whose built-in encoding has no glyph for ₹ (U+20B9) — it silently
    renders as a missing-glyph box. Caught by visually inspecting an
    actual generated receipt; guard against it reappearing."""
    pdf_amount = format_inr_for_pdf(150000)
    assert "₹" not in pdf_amount
    assert pdf_amount == "Rs. 1,500.00"


def test_amount_in_words_round_trip_sanity():
    words = amount_in_paise_to_words(150000)
    assert "One Thousand Five Hundred Rupees" in words
