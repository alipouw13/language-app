"""
Worksheet & exercise API routes.

POST /api/worksheets           — generate a scenario worksheet (persisted)
POST /api/worksheets/verb      — generate a verb-focused worksheet (persisted)
POST /api/worksheets/preview   — generate a scenario worksheet without saving
GET  /api/worksheets/verbs     — curated verb list for a language
GET  /api/worksheets/{id}      — retrieve a persisted lesson
POST /api/worksheets/evaluate  — evaluate a user's exercise answer
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.entra import Principal, get_principal
from app.models.pydantic_models import (
    ExerciseEvaluation,
    ExerciseSubmission,
    VerbWorksheetRequest,
    WorksheetRequest,
    WorksheetResponse,
)
from app.repository import store
from app.services import verbs
from app.services.evaluation_service import evaluate_answer
from app.services.worksheet_generator import (
    generate_and_persist_scenario,
    generate_and_persist_verb,
    generate_worksheet,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/worksheets",
    tags=["worksheets"],
    dependencies=[Depends(get_principal)],
)


@router.post("", response_model=dict)
async def create_worksheet(
    req: WorksheetRequest,
    principal: Principal = Depends(get_principal),
):
    """Generate a scenario-based worksheet and persist it."""
    try:
        user_id = await store.get_or_create_user(principal.id, display_name=principal.name or "Learner")
        lesson_id, worksheet, exercise_ids = await generate_and_persist_scenario(req, user_id)
        return {
            "lesson_id": lesson_id,
            "worksheet": worksheet.model_dump(),
            "exercise_ids": exercise_ids,
        }
    except Exception as exc:
        logger.exception("Failed to create worksheet")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/verb", response_model=dict)
async def create_verb_worksheet(
    req: VerbWorksheetRequest,
    principal: Principal = Depends(get_principal),
):
    """Generate a verb-focused worksheet (translations + real usage) and persist it."""
    try:
        user_id = await store.get_or_create_user(principal.id, display_name=principal.name or "Learner")
        lesson_id, worksheet, exercise_ids = await generate_and_persist_verb(req, user_id)
        return {
            "lesson_id": lesson_id,
            "worksheet": worksheet.model_dump(),
            "exercise_ids": exercise_ids,
        }
    except Exception as exc:
        logger.exception("Failed to create verb worksheet")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/preview", response_model=WorksheetResponse)
async def preview_worksheet(req: WorksheetRequest):
    """Generate a worksheet without saving (dry-run)."""
    try:
        return await generate_worksheet(req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/verbs")
async def get_verbs(language: str = Query("fr", pattern=r"^(en|fr|es)$")):
    """Curated common-verb list for the verb picker."""
    return {"language": language, "verbs": verbs.list_verbs(language)}


@router.get("/{lesson_id}")
async def get_lesson(lesson_id: str):
    """Retrieve a saved lesson by id."""
    lesson = await store.get_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {
        "id": lesson["id"],
        "target_language": lesson["target_language"],
        "scenario": lesson["scenario"],
        "mode": lesson.get("mode") or "scenario",
        "verb": lesson.get("verb"),
        "grammar_focus": lesson.get("grammar_focus"),
        "difficulty": lesson["difficulty"],
        "worksheet": lesson["worksheet"],
        "version": lesson["version"],
        "created_at": lesson["created_at"],
        "exercises": [
            {
                "id": ex["id"],
                "type": ex["exercise_type"],
                "question": ex["question"],
                "hint": ex.get("hint"),
                "order_index": ex["order_index"],
            }
            for ex in lesson["exercises"]
        ],
    }


@router.post("/evaluate", response_model=ExerciseEvaluation)
async def evaluate_exercise(
    submission: ExerciseSubmission,
    principal: Principal = Depends(get_principal),
):
    """Evaluate a user's answer to an exercise."""
    try:
        user_id = await store.get_or_create_user(principal.id, display_name=principal.name or "Learner")
        return await evaluate_answer(submission, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Evaluation failed")
        raise HTTPException(status_code=500, detail=str(exc))
