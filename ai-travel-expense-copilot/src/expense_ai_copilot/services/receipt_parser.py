from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedReceipt:
    vendor: str | None
    amount: float | None
    currency: str | None
    detected_expense_type: str | None
    raw_text: str


class ReceiptParser:
    """Rule-based receipt parser for local demos.

    This keeps the repository runnable without paid OCR or LLM APIs. Production versions
    can plug in OCR, document AI, or vision-language models behind the same interface.
    """

    EXPENSE_KEYWORDS = {
        "hotel": ["hotel", "stay", "room", "lodging"],
        "flight": ["flight", "airline", "boarding", "ticket"],
        "cab": ["cab", "taxi", "uber", "ola", "ride"],
        "meal": ["meal", "restaurant", "food", "lunch", "dinner"],
    }

    def parse(self, receipt_text: str) -> ParsedReceipt:
        amount = self._extract_amount(receipt_text)
        currency = self._extract_currency(receipt_text)
        expense_type = self._detect_expense_type(receipt_text)
        vendor = self._extract_vendor(receipt_text)
        return ParsedReceipt(
            vendor=vendor,
            amount=amount,
            currency=currency,
            detected_expense_type=expense_type,
            raw_text=receipt_text,
        )

    @staticmethod
    def _extract_amount(text: str) -> float | None:
        matches = re.findall(r"(?:INR|Rs\.?|₹|USD|EUR)?\s*([0-9]+(?:\.[0-9]{1,2})?)", text, flags=re.I)
        numeric_values = [float(value) for value in matches]
        return max(numeric_values) if numeric_values else None

    @staticmethod
    def _extract_currency(text: str) -> str | None:
        if re.search(r"\bINR\b|Rs\.?|₹", text, flags=re.I):
            return "INR"
        if re.search(r"\bUSD\b|\$", text, flags=re.I):
            return "USD"
        if re.search(r"\bEUR\b|€", text, flags=re.I):
            return "EUR"
        return None

    def _detect_expense_type(self, text: str) -> str | None:
        lowered = text.lower()
        for expense_type, keywords in self.EXPENSE_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return expense_type
        return None

    @staticmethod
    def _extract_vendor(text: str) -> str | None:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first_line and len(first_line) <= 80:
            return first_line
        return None
