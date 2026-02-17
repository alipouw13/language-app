"""
Worksheet & exercise API routes.

POST /api/worksheets        — generate a new worksheet
POST /api/worksheets/evaluate — evaluate a user's exercise answer
GET  /api/worksheets/{id}   — retrieve a persisted lesson
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.db_models import Lesson
from app.models.pydantic_models import (
    ExerciseEvaluation,
    ExerciseSubmission,
    LessonOut,
    WorksheetRequest,
    WorksheetResponse,
)
from app.services.evaluation_service import evaluate_answer
from app.services.worksheet_generator import generate_and_persist, generate_worksheet

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/worksheets", tags=["worksheets"])


@router.post("", response_model=dict)
async def create_worksheet(
    req: WorksheetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a scenario-based worksheet and persist it."""
    try:
        lesson_id, worksheet, exercise_ids = await generate_and_persist(req, db)
        return {
            "lesson_id": str(lesson_id),
            "worksheet": worksheet.model_dump(),
            "exercise_ids": [str(eid) for eid in exercise_ids],
        }
    except Exception as exc:
        logger.exception("Failed to create worksheet")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/preview", response_model=WorksheetResponse)
async def preview_worksheet(req: WorksheetRequest):
    """Generate a worksheet without saving (for preview / dry-run)."""
    try:
        return await generate_worksheet(req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{lesson_id}")
async def get_lesson(lesson_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retrieve a saved lesson by ID."""
    result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.exercises))
        .where(Lesson.id == lesson_id)
    )
    lesson = result.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    return {
        "id": str(lesson.id),
        "target_language": lesson.target_language,
        "scenario": lesson.scenario,
        "grammar_focus": lesson.grammar_focus,
        "difficulty": lesson.difficulty,
        "worksheet": lesson.worksheet_json,
        "version": lesson.version,
        "created_at": lesson.created_at.isoformat(),
        "exercises": [
            {
                "id": str(ex.id),
                "type": ex.exercise_type,
                "question": ex.question,
                "hint": ex.hint,
                "order_index": ex.order_index,
            }
            for ex in sorted(lesson.exercises, key=lambda e: e.order_index)
        ],
    }


@router.post("/evaluate", response_model=ExerciseEvaluation)
async def evaluate_exercise(
    submission: ExerciseSubmission,
    user_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Evaluate a user's answer to an exercise."""
    uid = user_id or uuid.uuid4()
    try:
        return await evaluate_answer(submission, uid, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
