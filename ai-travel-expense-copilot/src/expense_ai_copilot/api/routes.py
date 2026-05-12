from fastapi import APIRouter, Depends

from expense_ai_copilot.agents.claim_review_graph import ClaimReviewGraph, ClaimReviewState
from expense_ai_copilot.api.schemas import (
    ClaimReviewRequest,
    ClaimReviewResponse,
    HealthResponse,
    ReceiptParseRequest,
    ReceiptParseResponse,
)
from expense_ai_copilot.core.settings import Settings, get_settings
from expense_ai_copilot.services.receipt_parser import ReceiptParser

router = APIRouter(prefix="/api/v1", tags=["claims"])


def get_claim_graph(settings: Settings = Depends(get_settings)) -> ClaimReviewGraph:
    return ClaimReviewGraph(policy_dir=settings.policy_dir)


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)


@router.post("/receipts/parse", response_model=ReceiptParseResponse)
def parse_receipt(payload: ReceiptParseRequest) -> ReceiptParseResponse:
    parsed = ReceiptParser().parse(payload.receipt_text)
    return ReceiptParseResponse(
        vendor=parsed.vendor,
        amount=parsed.amount,
        currency=parsed.currency,
        detected_expense_type=parsed.detected_expense_type,
        raw_text=parsed.raw_text,
    )


@router.post("/claims/review", response_model=ClaimReviewResponse)
def review_claim(
    payload: ClaimReviewRequest,
    graph: ClaimReviewGraph = Depends(get_claim_graph),
) -> ClaimReviewResponse:
    final_state = graph.run(
        ClaimReviewState(
            employee_id=payload.employee_id,
            employee_grade=payload.employee_grade,
            expense_type=payload.expense_type.value,
            city=payload.city,
            amount=payload.amount,
            currency=payload.currency,
            receipt_text=payload.receipt_text,
        )
    )

    return ClaimReviewResponse(
        decision=final_state.decision,
        risk_score=final_state.risk_score,
        policy_references=final_state.policy_references,
        reasons=final_state.reasons,
        next_action=final_state.next_action,
    )
