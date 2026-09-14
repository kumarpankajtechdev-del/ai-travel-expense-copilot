"""Natural language -> typed plan -> allowlisted, parameterized SQLite query."""

import re

from expense_ai_copilot.models import QueryPlan
from expense_ai_copilot.store import Conflict


def demo_plan(question):
    text = question.lower().strip(" ?.")
    # Deliberately small grammar: unsupported questions are rejected instead of silently approximated.
    choices = {
        "show spending by category": ("category", "sum", "bar"),
        "spending by category": ("category", "sum", "bar"),
        "daily spending trend": ("date", "sum", "line"),
        "show daily spending": ("date", "sum", "line"),
        "top merchants": ("vendor", "sum", "bar"),
        "how much have i spent": ("total", "sum", "table"),
        "average expense by category": ("category", "average", "bar"),
        "how many expenses per category": ("category", "count", "bar"),
    }
    # Chart suffixes are supported explicitly. Filters belong to the visible filter controls.
    chart = None
    match = re.search(r" (?:as|in) (?:a )?(bar|line|donut|table)(?: chart)?$", text)
    if match:
        chart, text = match.group(1), text[: match.start()]
    if text not in choices:
        raise Conflict(
            "Offline demo supports the example questions shown in the app. "
            "Use the category/date controls for filters, or configure a live model for more phrasing."
        )
    group, metric, suggested = choices[text]
    return QueryPlan(
        supported=True,
        reason="Matched a documented offline example.",
        group_by=group,
        metric=metric,
        chart=chart or suggested,
    )


def run_analytics(value, store, model):
    trip = store.trip(value.trip_id)
    if model.settings.provider == "demo":
        plan, trace = demo_plan(value.question), {"provider": "demo", "method": "explicit intent grammar"}
    else:
        plan, trace = model.generate(
            "Convert the question into an expense aggregation plan. Available fields: category, date, vendor, "
            "amount. Metrics: sum, count, average. One trip only. No forecasting, joins, SQL, personal advice, "
            "currency conversion or arbitrary comparisons. Mark unsupported when the plan cannot answer the question. "
            "group_by=total for a single total. Select a useful chart. Use null for absent filters.",
            {"question": value.question, "trip_dates": [trip["start_date"], trip["end_date"]]},
            QueryPlan,
        )
    if not plan.supported:
        raise Conflict(plan.reason or "That question cannot be answered from the saved expenses.")
    updates = {
        key: getattr(value, key)
        for key in ("category", "start_date", "end_date")
        if getattr(value, key) is not None
    }
    if value.chart != "auto":
        updates["chart"] = value.chart
    plan = QueryPlan.model_validate({**plan.model_dump(), **updates})
    group = {"category": "category", "date": "date", "vendor": "vendor", "total": "'Total'"}[plan.group_by]
    metric = {"sum": "SUM(amount_cents)", "count": "COUNT(*)", "average": "AVG(amount_cents)"}[plan.metric]
    filters, params = ["trip_id=?"], [value.trip_id]
    for column, op, field in (
        ("category", "=", plan.category),
        ("date", ">=", plan.start_date),
        ("date", "<=", plan.end_date),
    ):
        if field is not None:
            filters.append(f"{column}{op}?")
            params.append(str(field))
    order = "label ASC" if plan.group_by == "date" else "value DESC, label ASC"
    grouping = "" if plan.group_by == "total" else f" GROUP BY {group}"
    sql = (
        f"SELECT {group} AS label, {metric} AS value, COUNT(*) AS expense_count "
        f"FROM expenses WHERE {' AND '.join(filters)}{grouping} ORDER BY {order} LIMIT 101"
    )
    with store.connect() as db:
        db.execute("PRAGMA query_only=ON")
        raw = [dict(row) for row in db.execute(sql, params)]
    rows = [
        {
            "label": row["label"],
            "value": round((row["value"] or 0) / (1 if plan.metric == "count" else 100), 2),
            "expense_count": row["expense_count"],
        }
        for row in raw[:100]
    ]
    return {
        "rows": rows,
        "chart": plan.chart,
        "metric": plan.metric,
        "unit": "expenses" if plan.metric == "count" else trip["currency"],
        "truncated": len(raw) > 100,
        "plan": plan.model_dump(mode="json"),
        "sql": sql,
        "parameters": params,
        "trace": trace,
    }
