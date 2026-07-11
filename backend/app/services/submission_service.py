"""
Worksheet submission service.

When a learner finishes a worksheet and submits it, this service builds an
authoritative, denormalized record of every exercise — the question, the
correct answer (from the store, not the client), the learner's answer, the
*first* score and the *corrected/final* score, attempt count and feedback —
and persists it to the Fabric OneLake Lakehouse as Delta tables
(``worksheet_submissions`` + ``worksheet_responses``) for Power BI reporting.

For any answered exercise the client never checked, the answer is evaluated
server-side at submit time so the recorded data is complete.
"""

from __future__ import annotations

import asyncio
import logging

from app.models.pydantic_models import (
    ExerciseSubmission,
    WorksheetResponseItem,
    WorksheetSubmissionResult,
)
from app.repository import store
from app.services.evaluation_service import evaluate_answer

logger = logging.getLogger(__name__)


async def submit_worksheet(
    lesson_id: str,
    items: list[WorksheetResponseItem],
    user_id: str,
) -> WorksheetSubmissionResult:
    """Resolve every exercise in the lesson, persist the submission, return summary."""
    lesson = await store.get_lesson(lesson_id)
    if lesson is None:
        raise ValueError(f"Lesson {lesson_id} not found")

    by_exercise: dict[str, WorksheetResponseItem] = {
        i.exercise_id: i for i in items if i.exercise_id
    }

    # Grade any answered-but-unscored exercises concurrently so submit doesn't
    # serialize N LLM round-trips.
    async def _maybe_eval(ex: dict):
        item = by_exercise.get(ex["id"])
        user_answer = (item.user_answer if item else "") or ""
        if user_answer.strip() and (item is None or item.final_score is None):
            try:
                return await evaluate_answer(
                    ExerciseSubmission(exercise_id=ex["id"], user_answer=user_answer),
                    user_id,
                )
            except Exception:
                logger.exception("Server-side evaluation failed for exercise %s", ex["id"])
        return None

    evals = await asyncio.gather(*(_maybe_eval(ex) for ex in lesson["exercises"]))

    resolved: list[dict] = []
    for ex, ev in zip(lesson["exercises"], evals):
        item = by_exercise.get(ex["id"])
        user_answer = (item.user_answer if item else "") or ""

        first_score = item.first_score if item else None
        first_is_correct = item.first_is_correct if item else None
        final_score = item.final_score if item else None
        final_is_correct = item.final_is_correct if item else None
        attempts = item.attempts if item else 0
        feedback = item.feedback if item else None

        # Complete the record server-side if answered but never scored.
        if ev is not None and final_score is None:
            final_score, final_is_correct, feedback = ev.score, ev.is_correct, ev.feedback
            attempts = max(attempts, 1)
            if first_score is None:
                first_score, first_is_correct = ev.score, ev.is_correct

        resolved.append(
            {
                "exercise_id": ex["id"],
                "order_index": ex.get("order_index", 0),
                "exercise_type": ex.get("exercise_type", ""),
                "question": ex.get("question", ""),
                "correct_answer": ex.get("correct_answer", ""),
                "user_answer": user_answer,
                "first_score": first_score,
                "first_is_correct": first_is_correct,
                "final_score": final_score,
                "final_is_correct": final_is_correct,
                "attempts": attempts,
                "feedback": feedback,
            }
        )

    summary = await store.create_worksheet_submission(
        user_id=user_id, lesson=lesson, responses=resolved
    )
    return WorksheetSubmissionResult(**summary)
