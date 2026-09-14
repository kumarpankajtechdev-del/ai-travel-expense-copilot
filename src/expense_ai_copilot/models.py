from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Currency = Literal["GBP", "EUR", "USD", "INR"]
Category = Literal["hotel", "meal", "transport", "flight", "activity", "other"]
Money = Annotated[Decimal, Field(gt=0, le=999999, max_digits=8, decimal_places=2)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def cents(value: Decimal | str | int) -> int:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Use a finite amount with no more than two decimal places.")
    return int(amount * 100)


class TripInput(Model):
    title: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=80)
    currency: Currency = "GBP"
    start_date: Date
    end_date: Date
    budget: Money = Decimal("650")
    hotel_nightly_limit: Money = Decimal("180")
    meal_daily_limit: Money = Decimal("60")

    @model_validator(mode="after")
    def dates_in_order(self):
        if not 0 <= (self.end_date - self.start_date).days <= 365:
            raise ValueError("A trip must end on or after its start, within 365 days.")
        return self


class Receipt(Model):
    vendor: str | None = Field(default=None, max_length=120)
    amount: Money | None = None
    currency: Currency | None = None
    date: Date | None = None
    category: Category | None = None
    units: int = Field(default=1, ge=1, le=60)


class ExpenseInput(Model):
    vendor: str = Field(min_length=1, max_length=120)
    amount: Money
    currency: Currency
    date: Date
    category: Category
    units: int = Field(default=1, ge=1, le=60)


class ReviewInput(Model):
    trip_id: str = Field(min_length=1, max_length=80)
    receipt_text: str = Field(min_length=5, max_length=12000)


class ConfirmInput(ExpenseInput):
    acknowledge_warnings: bool = False


class Question(Model):
    trip_id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=3, max_length=1000)


class QueryPlan(Model):
    supported: bool
    reason: str = Field(max_length=400)
    group_by: Literal["category", "date", "vendor", "total"]
    metric: Literal["sum", "count", "average"]
    category: Category | None = None
    start_date: Date | None = None
    end_date: Date | None = None
    chart: Literal["bar", "line", "donut", "table"] = "bar"

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("The start date must not be after the end date.")
        return self


class AnalyticsInput(Question):
    chart: Literal["auto", "bar", "line", "donut", "table"] = "auto"
    category: Category | None = None
    start_date: Date | None = None
    end_date: Date | None = None

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("The start date must not be after the end date.")
        return self


class GroundedAnswer(Model):
    answer: str = Field(min_length=1, max_length=1800)
    citation_ids: list[str] = Field(min_length=1, max_length=6)
