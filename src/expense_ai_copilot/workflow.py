"""A real LangGraph review, with durable drafts owned by the application."""

from __future__ import annotations

import re
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from expense_ai_copilot.llm import JsonModel, ProviderError
from expense_ai_copilot.models import GroundedAnswer, Receipt, cents
from expense_ai_copilot.receipts import parse_receipt


def assess(receipt, trip, daily_spend=0):
    issues, warnings = [], []
    for name in ("vendor", "amount", "currency", "date", "category"):
        if not getattr(receipt, name):
            issues.append(f"Enter a valid {name}.")
    if receipt.currency and receipt.currency != trip["currency"]:
        issues.append(f"This trip uses {trip['currency']}; currency conversion is not supported.")
    if receipt.date and not trip["start_date"] <= str(receipt.date) <= trip["end_date"]:
        issues.append("The expense date must fall within the trip dates.")
    if receipt.amount and receipt.currency == trip["currency"]:
        amount = cents(receipt.amount)
        if receipt.category == "hotel" and amount > trip["hotel_limit_cents"] * receipt.units:
            warnings.append("The hotel cost exceeds your nightly budget.")
        if receipt.category == "meal" and daily_spend + amount > trip["meal_limit_cents"]:
            warnings.append("Meals on this date exceed your daily budget, including saved expenses.")
        if trip["spent_cents"] + amount > trip["budget_cents"]:
            warnings.append("Adding this expense will exceed your total trip budget.")
    return issues, warnings


def rules(trip):
    currency = trip["currency"]
    return [
        {
            "id": "trip-budget",
            "text": f"Your total trip budget is {currency} {trip['budget_cents'] / 100:.2f}. "
            f"Confirmed expenses currently total {currency} {trip['spent_cents'] / 100:.2f}.",
        },
        {
            "id": "hotel-limit",
            "text": f"Your hotel budget is {currency} {trip['hotel_limit_cents'] / 100:.2f} "
            "per night. A receipt covering several nights is checked against the number of nights.",
        },
        {
            "id": "meal-limit",
            "text": f"Your meal budget is {currency} {trip['meal_limit_cents'] / 100:.2f} "
            "per day, including meals already saved for that day.",
        },
        {
            "id": "trip-dates",
            "text": f"Expenses must be dated from {trip['start_date']} to {trip['end_date']}, inclusive.",
        },
        {
            "id": "currency",
            "text": f"Only {currency} expenses can be saved in this trip. There is no automatic currency conversion.",
        },
        {
            "id": "confirmation",
            "text": "Every receipt requires your review and confirmation before it is saved. "
            "Budget warnings can be acknowledged; missing fields, invalid dates and currency mismatches must be corrected.",
        },
    ]


def retrieve(question, trip):
    # Transparent lexical retrieval over six personal rules, not an embedding service.
    tokens = set(re.findall(r"[a-z]+", question.lower()))
    aliases = {
        "dinner": "meal",
        "lunch": "meal",
        "breakfast": "meal",
        "meals": "meal",
        "stay": "hotel",
        "night": "hotel",
        "approve": "confirmation",
        "approval": "confirmation",
        "dates": "date",
        "remaining": "total",
    }
    tokens |= {aliases[t] for t in list(tokens) if t in aliases}
    scored = []
    for rule in rules(trip):
        words = set(re.findall(r"[a-z]+", (rule["id"] + " " + rule["text"]).lower()))
        score = len(tokens & words)
        if score:
            scored.append((score, rule))
    return [rule for _, rule in sorted(scored, key=lambda pair: -pair[0])[:3]]


def answer_question(question, trip, model: JsonModel):
    sources = retrieve(question, trip)
    if not sources:
        return {
            "answer": "I can explain this trip's budget, hotel and meal limits, dates, currency and confirmation rules.",
            "sources": [],
            "mode": model.settings.provider,
            "trace": [],
        }
    if model.settings.provider == "demo":
        return {
            "answer": " ".join(s["text"] for s in sources),
            "sources": sources,
            "mode": "demo",
            "trace": [{"step": "lexical retrieval; extractive answer"}],
        }
    answer, trace = model.generate(
        "Answer only questions about the supplied personal travel rules. Use only the sources, "
        "cite their IDs, and say when they do not answer the question. Do not offer employer-policy advice.",
        {"question": question, "sources": sources},
        GroundedAnswer,
    )
    allowed = {s["id"] for s in sources}
    if not set(answer.citation_ids) <= allowed:
        raise ProviderError("The model returned an unknown source. Please try a narrower question.")
    return {
        "answer": answer.answer,
        "sources": [s for s in sources if s["id"] in answer.citation_ids],
        "mode": model.settings.provider,
        "trace": [trace],
    }


class ReviewState(TypedDict, total=False):
    trip: dict
    text: str
    receipt: dict
    sources: list
    issues: list
    warnings: list
    trace: list
    mode: str


def review_receipt(store, trip_id, text, model: JsonModel):
    trip = store.trip(trip_id)
    existing = store.existing_review(trip_id, text)
    if existing:
        return existing

    def extract(state):
        started = time.perf_counter()
        if model.settings.provider == "demo":
            receipt = parse_receipt(state["text"])
            metrics = {"provider": "demo", "method": "label-based parser; no model call"}
        else:
            receipt, metrics = model.generate(
                "Extract a receipt. Use null for unknown or ambiguous fields. Never infer a missing date, "
                "currency or amount from the trip. amount is the grand total, not a reference or subtotal. "
                "units is hotel nights (1 if not stated). category is hotel, meal, transport, flight, activity or other.",
                {"receipt_text": state["text"]},
                Receipt,
            )
        return {
            "receipt": receipt.model_dump(mode="json"),
            "trace": [
                {"step": "extract", "duration_ms": round((time.perf_counter() - started) * 1000), **metrics}
            ],
        }

    def retrieve_rules(state):
        receipt = state["receipt"]
        sources = retrieve(f"{receipt.get('category') or ''} total budget currency dates confirmation", trip)
        return {
            "sources": sources,
            "trace": state["trace"] + [{"step": "retrieve_personal_rules", "source_count": len(sources)}],
        }

    def validate(state):
        receipt = Receipt.model_validate(state["receipt"])
        daily = (
            store.daily_spend(trip_id, receipt.category, receipt.date)
            if receipt.date and receipt.category
            else 0
        )
        issues, warnings = assess(receipt, trip, daily)
        return {
            "issues": issues,
            "warnings": warnings,
            "trace": state["trace"]
            + [
                {"step": "validate_budget", "issues": len(issues), "warnings": len(warnings)},
                {"step": "await_user_confirmation"},
            ],
        }

    graph = StateGraph(ReviewState)
    graph.add_node("extract", extract)
    graph.add_node("retrieve_rules", retrieve_rules)
    graph.add_node("validate", validate)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "retrieve_rules")
    graph.add_edge("retrieve_rules", "validate")
    graph.add_edge("validate", END)
    result = graph.compile().invoke({"text": text, "trip": trip, "mode": model.settings.provider})
    # Raw receipt text is deliberately not persisted. Draft fields and trace survive restart.
    saved = {key: result[key] for key in ("receipt", "sources", "issues", "warnings", "trace", "mode")}
    return store.create_review(trip_id, text, saved)
