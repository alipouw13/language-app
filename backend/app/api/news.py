"""
Current-events news API routes (Fabric Real-Time Intelligence hot path).

GET /api/news/topics   — today's enriched headlines in a target language,
                         graded near the learner's CEFR level. Optionally
                         personalized toward the learner's weak skills.
GET /api/news/{id}     — a single enriched news item.

These power the "Current Events" picker in the UI; the chosen ``news_id`` is then
passed to POST /api/conversations to start a conversation grounded in real news.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.entra import Principal, get_principal
from app.models.pydantic_models import LANG_PATTERN, LEVEL_PATTERN
from app.repository import store
from app.services import news_service

router = APIRouter(
    prefix="/api/news",
    tags=["news"],
    dependencies=[Depends(get_principal)],
)


@router.get("/topics")
async def list_topics(
    lang: str = Query(..., pattern=LANG_PATTERN),
    level: str | None = Query(None, pattern=LEVEL_PATTERN),
    limit: int = Query(12, ge=1, le=50),
    personalized: bool = Query(False),
    principal: Principal = Depends(get_principal),
):
    """Today's current-events topics in ``lang``, optionally personalized."""
    user_id = None
    if personalized:
        user_id = await store.get_or_create_user(
            principal.id, display_name=principal.name or "Learner"
        )
    items = await news_service.get_topics(
        lang,
        level=level,
        limit=limit,
        user_id=user_id,
        personalized=personalized,
    )
    return {"items": items, "language": lang, "level": level, "count": len(items)}


@router.get("/{news_id}")
async def get_topic(
    news_id: str,
    principal: Principal = Depends(get_principal),
):
    """A single enriched news item."""
    item = await news_service.get_article(news_id)
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    return item
