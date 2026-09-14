from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from expense_ai_copilot.analytics import demo_plan, run_analytics
from expense_ai_copilot.llm import JsonModel
from expense_ai_copilot.main import create_app
from expense_ai_copilot.models import AnalyticsInput, ExpenseInput, TripInput
from expense_ai_copilot.receipts import parse_receipt
from expense_ai_copilot.settings import Settings
from expense_ai_copilot.store import Conflict, Store
from expense_ai_copilot.workflow import review_receipt

TRIP = "london-weekend"
TEXT = "Harbour Café\n2026-08-16\nDinner\nReference: 999999999\nTotal: GBP 32.50"
EXPENSE = dict(
    vendor="Harbour Café", amount="32.50", currency="GBP", date="2026-08-16", category="meal", units=1
)


@pytest.fixture
def setup(tmp_path):
    settings = Settings(data_dir=tmp_path, _env_file=None)
    store = Store(tmp_path / "tripledger.sqlite3")
    store.initialize()
    return store, JsonModel(settings), settings


@pytest.mark.parametrize(
    "text,expected",
    [
        (TEXT, Decimal("32.50")),
        ("Hotel\n2026-08-15\nRef: 999999\nSubtotal: GBP 180\nGrand total: GBP 210.00", Decimal("210")),
        ("Taxi\n2026-08-15\nBooking: 987654321", None),
        ("Hotel\nSubtotal: GBP 80.00\nTax: GBP 20.00", None),
        ("Café\nTotal: GBP 100.999", None),
        ("Café\nTotal: GBP 0.00", None),
        ("Café\nTotal: GBP 30\nTotal: GBP 35", None),
        ("Hotel\nGrand total: GBP 1,250.75", Decimal("1250.75")),
    ],
)
def test_receipt_totals_are_not_reference_numbers(text, expected):
    assert parse_receipt(text).amount == expected


def test_ambiguous_currency_and_date_require_review():
    result = parse_receipt("Hotel\n2026-08-14\n2026-08-15\nTotal: GBP 100\nEUR 120")
    assert result.currency is None
    assert result.date is None


def test_durable_review_confirmation_and_idempotency(setup):
    store, model, settings = setup
    draft = review_receipt(store, TRIP, TEXT, model)
    assert store.trip(TRIP)["spent_cents"] == 45420
    assert [t["step"] for t in draft["trace"]] == [
        "extract",
        "retrieve_personal_rules",
        "validate_budget",
        "await_user_confirmation",
    ]
    reopened = Store(settings.data_dir / "tripledger.sqlite3")
    assert reopened.reviews(TRIP)[0]["id"] == draft["id"]
    saved = reopened.confirm(draft["id"], ExpenseInput(**EXPENSE), False)
    again = reopened.confirm(draft["id"], ExpenseInput(**EXPENSE), False)
    assert again["id"] == saved["id"]
    assert reopened.trip(TRIP)["spent_cents"] == 48670
    assert review_receipt(store, TRIP, TEXT.lower(), model)["id"] == draft["id"]
    assert reopened.reviews(TRIP) == []


def test_concurrent_duplicate_reviews_only_create_one_draft(setup):
    store, model, _ = setup
    with ThreadPoolExecutor(max_workers=4) as pool:
        drafts = list(pool.map(lambda _: review_receipt(store, TRIP, TEXT, model), range(4)))
    assert len({draft["id"] for draft in drafts}) == 1
    assert len(store.reviews(TRIP)) == 1


def test_confirm_rechecks_budget_after_other_receipt(setup):
    store, model, _ = setup
    first = review_receipt(store, TRIP, TEXT, model)
    second = review_receipt(store, TRIP, TEXT.replace("Café", "Bistro").replace("32.50", "20.00"), model)
    assert second["warnings"] == []
    store.confirm(first["id"], ExpenseInput(**EXPENSE), False)
    value = ExpenseInput(**{**EXPENSE, "vendor": "Bistro", "amount": "20"})
    with pytest.raises(Conflict, match="daily budget"):
        store.confirm(second["id"], value, False)
    store.confirm(second["id"], value, True)
    assert store.trip(TRIP)["spent_cents"] == 50670


@pytest.mark.parametrize("change", [{"currency": "EUR"}, {"date": "2027-01-01"}])
def test_confirmation_revalidates_edited_fields(setup, change):
    store, model, _ = setup
    draft = review_receipt(store, TRIP, TEXT, model)
    with pytest.raises(Conflict):
        store.confirm(draft["id"], ExpenseInput(**{**EXPENSE, **change}), True)
    assert store.trip(TRIP)["expense_count"] == 8


def test_discard_is_idempotent_and_cannot_confirm(setup):
    store, model, _ = setup
    draft = review_receipt(store, TRIP, TEXT, model)
    assert store.discard(draft["id"]) == store.discard(draft["id"])
    with pytest.raises(Conflict, match="discarded"):
        store.confirm(draft["id"], ExpenseInput(**EXPENSE), True)


def test_analytics_filters_and_trip_isolation(setup):
    store, model, _ = setup
    result = run_analytics(
        AnalyticsInput(
            trip_id=TRIP, question="Show spending by category", category="meal", start_date="2026-08-16"
        ),
        store,
        model,
    )
    assert result["rows"] == [{"label": "meal", "value": 17.5, "expense_count": 1}]
    assert "?" in result["sql"] and TRIP not in result["sql"]
    trip = store.create_trip(
        TripInput(title="Empty trip", city="London", start_date="2026-08-14", end_date="2026-08-16")
    )
    result = run_analytics(
        AnalyticsInput(trip_id=trip["id"], question="How much have I spent?"), store, model
    )
    assert result["rows"][0]["value"] == 0


@pytest.mark.parametrize(
    "question",
    ["DROP TABLE expenses", "Predict next year's costs", "Show spending by category except hotels"],
)
def test_demo_does_not_approximate_unsupported_questions(question):
    with pytest.raises(Conflict):
        demo_plan(question)


def test_decimal_precision():
    with pytest.raises(ValidationError):
        ExpenseInput(**{**EXPENSE, "amount": "32.501"})
    with pytest.raises(ValidationError):
        ExpenseInput(**{**EXPENSE, "amount": "NaN"})


def test_browser_api_journey_without_provider_network(setup, monkeypatch):
    store, _, settings = setup

    def forbidden(*args, **kwargs):
        raise AssertionError("Demo attempted an external model call")

    monkeypatch.setattr(httpx.Client, "post", forbidden)
    # TestClient.post uses the inherited request path, so patch the provider's generate too.
    monkeypatch.setattr(JsonModel, "generate", forbidden)
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/assets/app.js").status_code == 200
        assert "api_key" not in client.get("/api/meta").text
        draft = client.request("POST", "/api/reviews", json={"trip_id": TRIP, "receipt_text": TEXT}).json()
        assert draft["status"] == "pending"
        response = client.request("POST", "/api/reviews/" + draft["id"] + "/confirm", json=EXPENSE)
        assert response.status_code == 200
        answer = client.request(
            "POST", "/api/rules/ask", json={"trip_id": TRIP, "question": "What is my meal budget?"}
        ).json()
        assert any(s["id"] == "meal-limit" for s in answer["sources"])
        assert client.get("/api/trips/" + TRIP + "/export").status_code == 200
        assert (
            client.request(
                "POST",
                "/api/reviews",
                json={"trip_id": TRIP, "receipt_text": TEXT},
                headers={"Origin": "https://unrelated.example"},
            ).status_code
            == 403
        )
        assert client.get("/api/trips/unknown").status_code == 404
