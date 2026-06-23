"""
Lessons library API routes — paginated access to the current user's saved
worksheets, conversations and worksheet submissions.

GET /api/lessons                    — paginated lesson list
GET /api/lessons/conversations      — paginated conversation list
GET /api/lessons/submissions        — paginated worksheet-submission list
GET /api/lessons/submissions/{id}   — a submission with its response detail
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

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


@router.get("/submissions")
async def list_submissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    """Paginated list of the current user's worksheet submissions (progress)."""
    items, total = await store.list_submissions(principal.id, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: str,
    principal: Principal = Depends(get_principal),
):
    """A worksheet submission with its per-exercise response detail."""
    submission = await store.get_submission(submission_id)
    if submission is None or submission.get("user_id") != principal.id:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission
