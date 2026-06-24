"""
FastAPI application entry point.

Registers routers, middleware and the startup hook. Persistence is the Fabric
OneLake Lakehouse (Delta tables); all Azure services authenticate with
Microsoft Entra ID. Run with: uvicorn app.main:app --reload
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, conversations, lessons, news, speech, translate, worksheets
from app.config import get_settings
from app.repository import store
from app.services import news_ingestion

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify the lakehouse backend is reachable and ensure all tables exist."""
    health = await store.ensure_ready()
    if health.get("status") != "ok":
        logger.warning("Lakehouse storage not ready: %s", health)
    else:
        logger.info("Lakehouse storage ready: %s", health)
        # Create every Delta table up front so the lakehouse is fully
        # provisioned before the first worksheet/submission is written.
        try:
            await store.ensure_tables()
        except Exception:
            logger.exception("Failed to ensure lakehouse tables")
    if not settings.entra_auth_enabled:
        logger.warning(
            "ENTRA_AUTH_ENABLED is false — API auth is DISABLED (development mode)."
        )

    poller_task: asyncio.Task | None = None
    stop_event = asyncio.Event()
    if settings.news_poll_enabled:
        poller_task = asyncio.create_task(news_ingestion.run_poller(stop_event))

    yield

    if poller_task is not None:
        stop_event.set()
        poller_task.cancel()
        with suppress(asyncio.CancelledError):
            await poller_task


app = FastAPI(
    title="Language Learning API",
    description="AI-powered language learning on Azure AI Foundry + Fabric OneLake",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(worksheets.router)
app.include_router(conversations.router)
app.include_router(lessons.router)
app.include_router(news.router)
app.include_router(speech.router)
app.include_router(translate.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    return {"message": "Language Learning API v2.0"}


@app.get("/health")
async def health():
    storage = await store.ensure_ready()
    return {
        "status": "healthy",
        "version": "2.0.0",
        "auth_enabled": settings.entra_auth_enabled,
        "storage": storage,
    }
