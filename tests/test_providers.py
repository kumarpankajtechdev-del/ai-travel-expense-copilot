import json

import httpx
import pytest

from expense_ai_copilot.llm import JsonModel, ProviderError, strict_schema
from expense_ai_copilot.models import GroundedAnswer, Receipt
from expense_ai_copilot.settings import Settings
from expense_ai_copilot.workflow import answer_question

RECEIPT = {
    "vendor": "Example Café",
    "amount": "25.50",
    "currency": "GBP",
    "date": "2026-08-16",
    "category": "meal",
    "units": 1,
}


def adapter(provider, payload, code=200, inspect=None):
    def handler(request):
        if inspect:
            inspect(request, json.loads(request.content))
        return httpx.Response(code, json=payload)

    return JsonModel(
        Settings(provider=provider, model="test-model", api_key="test-key", _env_file=None),
        httpx.MockTransport(handler),
    )


def openai_payload(value):
    return {
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]},
        ],
    }


def test_openai_response_and_strict_schema():
    def inspect(request, body):
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert body["store"] is False
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["additionalProperties"] is False

    parsed, _ = adapter("openai", openai_payload(RECEIPT), inspect=inspect).generate("extract", {}, Receipt)
    assert str(parsed.amount) == "25.50"
    schema = strict_schema(Receipt)
    assert set(schema["required"]) == set(schema["properties"])


def test_anthropic_forced_tool():
    def inspect(request, body):
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        assert body["tool_choice"] == {"type": "tool", "name": "emit_result"}

    payload = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "name": "emit_result", "input": RECEIPT}],
    }
    parsed, _ = adapter("anthropic", payload, inspect=inspect).generate("extract", {}, Receipt)
    assert parsed.vendor == "Example Café"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"status": "incomplete"},
        {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]},
        openai_payload({**RECEIPT, "amount": "-2"}),
        openai_payload({**RECEIPT, "extra": "injected"}),
        {
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "not json"}]}],
        },
    ],
)
def test_invalid_model_result_fails_closed(payload):
    with pytest.raises(ProviderError):
        adapter("openai", payload).generate("extract", {}, Receipt)


def test_http_errors_do_not_expose_provider_body():
    with pytest.raises(ProviderError) as error:
        adapter("openai", {"error": "secret-test-key"}, code=401).generate("extract", {}, Receipt)
    assert "secret-test-key" not in str(error.value)


def test_unknown_citation_is_rejected():
    model = adapter("openai", openai_payload({"answer": "Wrong", "citation_ids": ["invented-source"]}))
    trip = {
        "currency": "GBP",
        "budget_cents": 65000,
        "spent_cents": 0,
        "hotel_limit_cents": 18000,
        "meal_limit_cents": 6000,
        "start_date": "2026-08-14",
        "end_date": "2026-08-16",
    }
    with pytest.raises(ProviderError, match="unknown source"):
        answer_question("What is my meal budget?", trip, model)
    assert strict_schema(GroundedAnswer)["required"] == ["answer", "citation_ids"]
