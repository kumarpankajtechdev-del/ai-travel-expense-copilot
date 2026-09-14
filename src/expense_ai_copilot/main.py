from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from expense_ai_copilot.analytics import run_analytics
from expense_ai_copilot.llm import JsonModel, ProviderError
from expense_ai_copilot.models import (
    AnalyticsInput,
    ConfirmInput,
    ExpenseInput,
    Question,
    ReviewInput,
    TripInput,
)
from expense_ai_copilot.settings import Settings
from expense_ai_copilot.store import Conflict, Store
from expense_ai_copilot.workflow import answer_question, review_receipt


def create_app(settings=None, model=None):
    settings = settings or Settings()
    store = Store(settings.data_dir / "tripledger.sqlite3")
    model = model or JsonModel(settings)
    assets = Path(__file__).parent / "assets"

    @asynccontextmanager
    async def lifespan(app):
        store.initialize()
        yield

    app = FastAPI(title="TripLedger — personal travel copilot", version="0.2.0", lifespan=lifespan)
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_browser_boundary(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Use the app from the same local address."}, status_code=403)
            if (
                request.method != "DELETE"
                and request.headers.get("content-type", "").split(";")[0] != "application/json"
            ):
                return JSONResponse({"detail": "Send application/json."}, status_code=415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            )
        return response

    @app.exception_handler(KeyError)
    async def missing(request, error):
        return JSONResponse({"detail": error.args[0]}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(ProviderError)
    async def provider_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=502)

    @app.get("/")
    def index():
        return FileResponse(assets / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": settings.provider}

    @app.get("/api/meta")
    def meta():
        return {
            "name": "TripLedger",
            "mode": settings.provider,
            "model": settings.model,
            "sample_data": "The London weekend trip contains fictional personal expenses.",
        }

    @app.get("/api/trips")
    def trips():
        return store.trips()

    @app.post("/api/trips", status_code=201)
    def add_trip(value: TripInput):
        return store.create_trip(value)

    @app.get("/api/trips/{trip_id}")
    def trip(trip_id: str):
        return {
            "trip": store.trip(trip_id),
            "expenses": store.expenses(trip_id),
            "reviews": store.reviews(trip_id),
        }

    @app.post("/api/reviews")
    def review(value: ReviewInput):
        return review_receipt(store, value.trip_id, value.receipt_text, model)

    @app.post("/api/reviews/{review_id}/confirm")
    def confirm(review_id: str, value: ConfirmInput):
        fields = value.model_dump(exclude={"acknowledge_warnings"})
        return store.confirm(review_id, ExpenseInput.model_validate(fields), value.acknowledge_warnings)

    @app.post("/api/reviews/{review_id}/discard")
    def discard(review_id: str):
        return store.discard(review_id)

    @app.post("/api/analytics")
    def analytics(value: AnalyticsInput):
        return run_analytics(value, store, model)

    @app.post("/api/rules/ask")
    def ask(value: Question):
        return answer_question(value.question, store.trip(value.trip_id), model)

    @app.get("/api/trips/{trip_id}/events")
    def events(trip_id: str):
        return store.events(trip_id)

    @app.get("/api/trips/{trip_id}/export")
    def export(trip_id: str):
        rows = store.expenses(trip_id)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["date", "vendor", "category", "amount", "currency", "nights"])
        for row in rows:
            vendor = row["vendor"]
            if vendor.lstrip().startswith(("=", "+", "-", "@")):
                vendor = "'" + vendor
            writer.writerow(
                [
                    row["date"],
                    vendor,
                    row["category"],
                    f"{row['amount_cents'] / 100:.2f}",
                    row["currency"],
                    row["units"],
                ]
            )
        return Response(
            buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="trip-expenses.csv"'},
        )

    app.mount("/assets", StaticFiles(directory=assets), name="assets")
    return app
