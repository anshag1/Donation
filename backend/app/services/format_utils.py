"""Currency display formatting shared by the PDF and email templates.
Indian digit grouping (e.g. 1,23,456) — see docs/05-architecture.md's
"currency always formatted via a single helper" coding standard.
"""


def _group_indian(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    last_three, rest = digits[-3:], digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return ",".join([*groups, last_three])


def format_inr(amount_in_paise: int) -> str:
    rupees, paise = divmod(amount_in_paise, 100)
    return f"₹{_group_indian(str(rupees))}.{paise:02d}"


def format_inr_for_pdf(amount_in_paise: int) -> str:
    """Same formatting as format_inr(), but with an "Rs." prefix instead of
    the ₹ glyph (U+20B9). ReportLab's PDF receipts use the base-14 Helvetica
    font — guaranteed present in any PDF viewer without embedding — whose
    built-in encoding predates the Rupee sign and renders it as a missing-
    glyph box. Embedding a Unicode TTF just for this one symbol isn't
    worth the added binary asset and font-availability risk across
    deployment environments; "Rs." is standard on real financial documents
    for exactly this reason. Email/web displays keep the ₹ glyph via
    format_inr() since browsers and mail clients render it correctly.
    """
    rupees, paise = divmod(amount_in_paise, 100)
    return f"Rs. {_group_indian(str(rupees))}.{paise:02d}"
