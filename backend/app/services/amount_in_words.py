"""Converts a rupee amount to words using the Indian numbering system
(lakh/crore), for the receipt PDF's "Amount in Words" field."""

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety",
]


def _two_digits(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return f"{_TENS[tens]} {_ONES[ones]}".strip()


def _three_digits(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    if hundreds and rest:
        return f"{_ONES[hundreds]} Hundred {_two_digits(rest)}"
    if hundreds:
        return f"{_ONES[hundreds]} Hundred"
    return _two_digits(rest)


def rupees_to_words(rupees: int) -> str:
    if rupees == 0:
        return "Zero Rupees Only"

    crore, remainder = divmod(rupees, 10_000_000)
    lakh, remainder = divmod(remainder, 100_000)
    thousand, hundreds = divmod(remainder, 1000)

    parts = []
    if crore:
        parts.append(f"{_three_digits(crore)} Crore")
    if lakh:
        parts.append(f"{_three_digits(lakh)} Lakh")
    if thousand:
        parts.append(f"{_three_digits(thousand)} Thousand")
    if hundreds:
        parts.append(_three_digits(hundreds))

    return f"{' '.join(parts)} Rupees Only"


def amount_in_paise_to_words(amount_in_paise: int) -> str:
    rupees, paise = divmod(amount_in_paise, 100)
    words = rupees_to_words(rupees)
    if paise:
        words = words.replace(" Rupees Only", f" Rupees and {_two_digits(paise)} Paise Only")
    return words
