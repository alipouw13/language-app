"""
FastAPI application entry point.

Registers routers, middleware, and startup hooks.
Run with: uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conversations, lessons, worksheets
from app.config import get_settings
from app.db.session import init_db
from app.models.db_models import Base

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)

app = FastAPI(
    title="Language Learning API",
    description="Production-grade API for AI-powered language learning",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(worksheets.router)
app.include_router(conversations.router)
app.include_router(lessons.router)


@app.on_event("startup")
async def on_startup():
    """Initialise DB connection (with retries) and create tables if needed.
    In production, use Alembic migrations instead of create_all.
    """
    await init_db()

    # Import engine after init_db has populated it
    from app.db.session import engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root():
    return {"message": "Language Learning API v1.0"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.0.0",
    }
