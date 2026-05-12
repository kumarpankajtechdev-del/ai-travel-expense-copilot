from pathlib import Path

from expense_ai_copilot.agents.claim_review_graph import ClaimReviewGraph, ClaimReviewState


def test_claim_review_graph_approves_valid_hotel_claim():
    graph = ClaimReviewGraph(policy_dir=Path("sample_data/policies"))

    final_state = graph.run(
        ClaimReviewState(
            employee_id="EMP-1001",
            employee_grade="L4",
            expense_type="hotel",
            city="Mumbai",
            amount=4200,
            currency="INR",
            receipt_text="Blue Orchid Hotel Mumbai Hotel stay Mumbai Room charge INR 4200",
        )
    )

    assert final_state.decision == "approved"
    assert final_state.risk_score < 0.30
    assert final_state.policy_references


def test_claim_review_graph_flags_expensive_hotel_claim():
    graph = ClaimReviewGraph(policy_dir=Path("sample_data/policies"))

    final_state = graph.run(
        ClaimReviewState(
            employee_id="EMP-1002",
            employee_grade="L3",
            expense_type="hotel",
            city="Delhi",
            amount=6200,
            currency="INR",
            receipt_text="Hotel stay Delhi Room charge INR 6200",
        )
    )

    assert final_state.decision in {"needs_review", "rejected"}
    assert final_state.risk_score >= 0.30
