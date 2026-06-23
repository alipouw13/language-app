"""
Lessons library API routes — paginated access to the current user's saved
worksheets and conversations.

GET /api/lessons                — paginated lesson list
GET /api/lessons/conversations  — paginated conversation list
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.entra import Principal, get_principal
from app.repository import store

router = APIRouter(
    prefix="/api/lessons",
    tags=["lessons"],
    dependencies=[Depends(get_principal)],
)


@router.get("")
async def list_lessons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    """Paginated list of the current user's saved worksheet lessons."""
    items, total = await store.list_lessons(principal.id, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/conversations")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    """Paginated list of the current user's conversation sessions."""
    items, total = await store.list_conversations(principal.id, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}
