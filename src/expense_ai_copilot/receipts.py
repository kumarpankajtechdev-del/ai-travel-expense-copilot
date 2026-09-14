from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from expense_ai_copilot.models import Receipt

CATEGORIES = {
    "hotel": ("hotel", "room", "lodging", "hostel"),
    "meal": ("cafe", "café", "restaurant", "breakfast", "lunch", "dinner", "meal"),
    "transport": ("taxi", "cab", "uber", "train", "metro", "bus", "transport"),
    "flight": ("airline", "flight", "airways"),
    "activity": ("museum", "gallery", "tour", "admission", "activity"),
}
NUMBER = r"((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)(?![\d.])"
AMOUNT = re.compile(
    r"(?:GBP|EUR|USD|INR|£|€|\$|₹|Rs\.?)?\s*" + NUMBER + r"\s*(?:GBP|EUR|USD|INR)?\s*$",
    re.I,
)


def parse_receipt(text: str) -> Receipt:
    """Parse explicit totals only; dates, taxes and reference IDs are never amount fallbacks."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    total_lines = [line for line in lines if re.match(r"^grand\s+total\b", line, re.I)]
    if not total_lines:
        total_lines = [
            line
            for line in lines
            if re.match(r"^(?:total(?:\s+paid)?|amount\s+(?:due|paid)|room\s+charge|fare)\b", line, re.I)
        ]
    values = set()
    for line in total_lines:
        # Remove the label, then match the whole remainder to avoid grabbing a reference number.
        tail = re.sub(
            r"^(?:grand\s+total|total(?:\s+paid)?|amount\s+(?:due|paid)|room\s+charge|fare)\s*[:=]?\s*",
            "",
            line,
            flags=re.I,
        )
        match = AMOUNT.fullmatch(tail)
        if match:
            value = Decimal(match.group(1).replace(",", ""))
            if 0 < value <= 999999:
                values.add(value)
    currency_set = set()
    for code, pattern in {
        "GBP": r"\bGBP\b|£",
        "EUR": r"\bEUR\b|€",
        "USD": r"\bUSD\b|\$",
        "INR": r"\bINR\b|₹|\bRs\.?",
    }.items():
        if re.search(pattern, text, re.I):
            currency_set.add(code)
    found_dates = set()
    for pattern, fmt in [(r"\b\d{4}-\d{2}-\d{2}\b", "%Y-%m-%d"), (r"\b\d{2}/\d{2}/\d{4}\b", "%d/%m/%Y")]:
        for match in re.findall(pattern, text):
            try:
                found_dates.add(datetime.strptime(match, fmt).date())
            except ValueError:
                pass
    categories = [
        name
        for name, words in CATEGORIES.items()
        if any(re.search(r"\b" + re.escape(word) + r"\b", text, re.I) for word in words)
    ]
    units_match = re.search(r"\b(\d{1,2})\s+nights?\b", text, re.I)
    return Receipt(
        vendor=lines[0][:120] if lines else None,
        amount=next(iter(values)) if len(values) == 1 else None,
        currency=next(iter(currency_set)) if len(currency_set) == 1 else None,
        date=next(iter(found_dates)) if len(found_dates) == 1 else None,
        category=categories[0] if len(categories) == 1 else None,
        units=min(60, max(1, int(units_match.group(1)))) if units_match else 1,
    )
