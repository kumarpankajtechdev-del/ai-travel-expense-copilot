from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimFacts:
    employee_grade: str
    expense_type: str
    city: str
    amount: float
    currency: str
    receipt_text: str


@dataclass(frozen=True)
class ClaimDecision:
    decision: str
    risk_score: float
    reasons: list[str]
    next_action: str


class ClaimRuleEngine:
    """Deterministic policy rule engine for explainable decisions."""

    HOTEL_LIMITS_INR = {
        "L3": 3500,
        "L4": 5000,
        "L5": 7000,
        "L6": 9000,
    }
    CAB_LIMIT_INR = 2500
    MEAL_LIMIT_INR = 1500

    def evaluate(self, facts: ClaimFacts) -> ClaimDecision:
        reasons: list[str] = []
        risk = 0.05

        if facts.currency != "INR":
            risk += 0.20
            reasons.append("Non-INR claim requires finance review.")

        if facts.expense_type == "hotel":
            limit = self.HOTEL_LIMITS_INR.get(facts.employee_grade.upper(), 3000)
            if facts.amount <= limit:
                reasons.append("Amount is within allowed hotel limit for employee grade and city tier.")
            else:
                risk += 0.55
                reasons.append(f"Hotel amount exceeds grade limit of INR {limit}.")

        elif facts.expense_type == "cab":
            if facts.amount <= self.CAB_LIMIT_INR:
                reasons.append("Cab amount is within local transport threshold.")
            else:
                risk += 0.45
                reasons.append(f"Cab amount exceeds local transport threshold of INR {self.CAB_LIMIT_INR}.")

        elif facts.expense_type == "meal":
            if facts.amount <= self.MEAL_LIMIT_INR:
                reasons.append("Meal amount is within daily meal threshold.")
            else:
                risk += 0.35
                reasons.append(f"Meal amount exceeds meal threshold of INR {self.MEAL_LIMIT_INR}.")

        else:
            risk += 0.25
            reasons.append("Expense type requires manual category validation.")

        if facts.expense_type not in facts.receipt_text.lower():
            risk += 0.15
            reasons.append("Receipt text does not strongly match the claimed expense type.")
        else:
            reasons.append("Receipt text contains evidence matching the expense type.")

        risk = min(round(risk, 2), 1.0)
        if risk < 0.30:
            return ClaimDecision("approved", risk, reasons, "create_approval_event")
        if risk < 0.70:
            return ClaimDecision("needs_review", risk, reasons, "send_to_human_reviewer")
        return ClaimDecision("rejected", risk, reasons, "create_policy_violation_event")
