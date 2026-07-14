"""
Lessons library API routes — paginated access to the current user's saved
worksheets, conversations and worksheet submissions.

GET  /api/lessons                    — paginated lesson list
GET  /api/lessons/conversations      — paginated conversation list
GET  /api/lessons/submissions        — paginated worksheet-submission list
GET  /api/lessons/submissions/{id}   — a submission with its response detail
POST /api/lessons/export             — export selected worksheets as one document
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.auth.entra import Principal, get_principal
from app.models.pydantic_models import WorksheetExportRequest
from app.repository import store
from app.services import export_service

logger = logging.getLogger(__name__)

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


@router.post("/export")
async def export_worksheets(
    req: WorksheetExportRequest,
    principal: Principal = Depends(get_principal),
):
    """Export one or more saved worksheets as a single downloadable document.

    Fetches each requested lesson, keeps only those owned by the caller, and
    renders them into one self-contained HTML (default) or Markdown file with
    the full answer key so a learner can read or print them offline later.
    """
    # De-duplicate while preserving the caller's requested order.
    seen: set[str] = set()
    ordered_ids = [i for i in req.lesson_ids if not (i in seen or seen.add(i))]

    # Single table scan for all requested lessons (export only needs the
    # worksheet content, so we skip the per-lesson exercises scan).
    lessons_by_id = await store.get_lessons_by_ids(ordered_ids)
    lessons: list[dict] = []
    for lesson_id in ordered_ids:
        lesson = lessons_by_id.get(lesson_id)
        if lesson is None or lesson.get("user_id") != principal.id:
            # Silently skip lessons that don't exist or aren't the caller's, so
            # one stale id doesn't fail the whole export.
            continue
        lessons.append(lesson)

    if not lessons:
        raise HTTPException(status_code=404, detail="No matching worksheets found")

    try:
        content, media_type, filename = export_service.render_export(lessons, req.format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Worksheet export failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
