import os
import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.api.routes import alerts, analytics, predictions, admin

def create_app(pool: asyncpg.Pool) -> FastAPI:
    app = FastAPI(title="Pikud HaOref API", docs_url=None, redoc_url=None)

    cors_origins = os.environ.get("CORS_ORIGINS", os.environ.get("MINI_APP_URL", "*"))
    origins = [o.strip() for o in cors_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.state.pool = pool
    app.state.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    @app.get("/healthz")
    async def healthz():
        return JSONResponse({"status": "ok"})

    app.include_router(alerts.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(predictions.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")

    return app
