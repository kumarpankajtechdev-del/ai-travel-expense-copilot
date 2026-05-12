from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from expense_ai_copilot.services.claim_rules import ClaimFacts, ClaimRuleEngine
from expense_ai_copilot.services.policy_retriever import PolicyRetriever
from expense_ai_copilot.services.receipt_parser import ReceiptParser


@dataclass
class ClaimReviewState:
    employee_id: str
    employee_grade: str
    expense_type: str
    city: str
    amount: float
    currency: str
    receipt_text: str
    parsed_receipt: dict = field(default_factory=dict)
    policy_references: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    decision: str = "pending"
    next_action: str = "none"


class ClaimReviewGraph:
    """LangGraph-inspired deterministic workflow.

    The graph keeps each step explicit and testable:
    1. Parse receipt evidence
    2. Retrieve relevant policy chunks
    3. Evaluate business rules
    4. Produce final decision
    """

    def __init__(self, policy_dir: Path):
        self.receipt_parser = ReceiptParser()
        self.policy_retriever = PolicyRetriever(policy_dir)
        self.rule_engine = ClaimRuleEngine()

    def run(self, state: ClaimReviewState) -> ClaimReviewState:
        state = self._parse_receipt(state)
        state = self._retrieve_policy(state)
        state = self._evaluate_claim(state)
        return state

    def _parse_receipt(self, state: ClaimReviewState) -> ClaimReviewState:
        parsed = self.receipt_parser.parse(state.receipt_text)
        state.parsed_receipt = {
            "vendor": parsed.vendor,
            "amount": parsed.amount,
            "currency": parsed.currency,
            "detected_expense_type": parsed.detected_expense_type,
        }
        return state

    def _retrieve_policy(self, state: ClaimReviewState) -> ClaimReviewState:
        query = f"{state.employee_grade} {state.expense_type} {state.city} {state.amount} {state.currency}"
        chunks = self.policy_retriever.retrieve(query, top_k=3)
        state.policy_references = [chunk.text for chunk in chunks]
        return state

    def _evaluate_claim(self, state: ClaimReviewState) -> ClaimReviewState:
        facts = ClaimFacts(
            employee_grade=state.employee_grade,
            expense_type=state.expense_type,
            city=state.city,
            amount=state.amount,
            currency=state.currency,
            receipt_text=state.receipt_text,
        )
        decision = self.rule_engine.evaluate(facts)
        state.decision = decision.decision
        state.risk_score = decision.risk_score
        state.reasons = decision.reasons
        state.next_action = decision.next_action
        return state
