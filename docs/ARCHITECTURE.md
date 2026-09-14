# Design and API

## The boundaries

The frontend makes same-origin JSON requests to FastAPI. Receipt data passes through a real LangGraph graph. Model-based extraction is optional; validation and persistence always remain deterministic.

The review graph ends with a pending draft. A separate confirmation endpoint validates the user's corrected values and rechecks the current trip and daily totals in a SQLite write transaction. This prevents two confirmations from trusting the same stale budget snapshot.

Identical normalised receipt text is unique within a trip. Receipt confirmation is idempotent by review ID. Discarded drafts remain in history and cannot be confirmed. A corrected or distinct receipt can be reviewed separately. This is text-level duplicate detection, not fraud detection: rephrased duplicates are not guaranteed to be detected.

Analytics produces a typed QueryPlan. The application chooses fixed SQL expressions and parameterises all filter values. Each query is restricted to the requested trip, reads from a query-only connection and returns at most 100 groups. No model-generated SQL is executed. The chart shows at most 12 groups; the returned table can show 100.

Answers use lexical retrieval over six dynamically populated trip rules. Live generation must cite IDs drawn from the retrieved set. Citation-ID validation does not prove every generated statement is correct; that remains a model-quality concern to evaluate with real models.

## API routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /health | Local health and mode |
| GET | /api/meta | Public configuration without credentials |
| GET / POST | /api/trips | List or create trips |
| GET | /api/trips/{id} | Summary, expenses and pending reviews |
| POST | /api/reviews | Extract and check receipt text |
| POST | /api/reviews/{id}/confirm | Save validated user-confirmed fields |
| POST | /api/reviews/{id}/discard | Discard a pending draft |
| POST | /api/analytics | Question and filters to aggregate chart data |
| POST | /api/rules/ask | Grounded personal-budget answer |
| GET | /api/trips/{id}/events | Last 100 activity records |
| GET | /api/trips/{id}/export | CSV export |

Example receipt review:

~~~json
{
  "trip_id": "london-weekend",
  "receipt_text": "Harbour Café\n2026-08-16\nDinner\nTotal: GBP 32.50"
}
~~~

Example confirmation, using the returned review ID:

~~~json
{
  "vendor": "Harbour Café",
  "amount": "32.50",
  "currency": "GBP",
  "date": "2026-08-16",
  "category": "meal",
  "units": 1,
  "acknowledge_warnings": false
}
~~~

If current spending now exceeds a limit, confirmation returns 409 until the user acknowledges the warning. Incorrect dates/currencies cannot be overridden by acknowledgement.

## Deliberate trade-offs

- SQLite makes local installation simple. It is not presented as a multi-tenant cloud deployment.
- A small explicit offline grammar offers reproducible demonstrations without pretending to understand arbitrary requests.
- All HTML/CSS/JavaScript ships inside the Python wheel, so installation is independent of the source checkout.
- No secret appears in browser configuration. Errors omit provider response bodies.
- The default server binds to loopback. Same-origin checks and a host allowlist reduce accidental browser exposure; they do not replace authentication.
- A model's refusal or invalid result cannot write an expense.
