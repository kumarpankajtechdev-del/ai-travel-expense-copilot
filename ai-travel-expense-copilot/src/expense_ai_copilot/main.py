from fastapi import FastAPI

from expense_ai_copilot.api.routes import router
from expense_ai_copilot.core.settings import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-powered Travel and Expense claim review backend with policy-aware automation.",
)

app.include_router(router)
