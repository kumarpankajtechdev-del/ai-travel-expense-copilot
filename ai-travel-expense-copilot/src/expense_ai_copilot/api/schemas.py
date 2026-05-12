from enum import Enum
from pydantic import BaseModel, Field


class ExpenseType(str, Enum):
    flight = "flight"
    hotel = "hotel"
    cab = "cab"
    meal = "meal"
    other = "other"


class ClaimReviewRequest(BaseModel):
    employee_id: str = Field(..., examples=["EMP-1001"])
    employee_grade: str = Field(..., examples=["L4"])
    expense_type: ExpenseType
    city: str = Field(..., examples=["Mumbai"])
    amount: float = Field(..., gt=0, examples=[4200])
    currency: str = Field(default="INR", examples=["INR"])
    receipt_text: str = Field(..., examples=["Hotel stay Mumbai. Room charge INR 4200."])


class ClaimReviewResponse(BaseModel):
    decision: str
    risk_score: float
    policy_references: list[str]
    reasons: list[str]
    next_action: str


class ReceiptParseRequest(BaseModel):
    receipt_text: str


class ReceiptParseResponse(BaseModel):
    vendor: str | None
    amount: float | None
    currency: str | None
    detected_expense_type: str | None
    raw_text: str


class HealthResponse(BaseModel):
    status: str
    service: str
