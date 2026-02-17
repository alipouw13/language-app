"""
Exercise evaluation service.

Sends a user's answer plus the correct answer to the LLM
for nuanced scoring and feedback.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Exercise, ExerciseAttempt, User
from app.models.pydantic_models import ExerciseEvaluation, ExerciseSubmission
from app.services.llm_service import chat_completion_json

SYSTEM_PROMPT = """\
You are a language-learning exercise evaluator.
Given a correct answer and a user's attempt, respond with a JSON object:
{
  "is_correct": true/false,
  "score": 0.0 to 1.0,
  "feedback": "brief explanation of what was right/wrong"
}
Be encouraging. If almost correct, give partial credit.
Ignore case and punctuation differences when evaluating.
Accept equivalent answers (e.g., synonyms, different valid conjugations).
Return ONLY valid JSON."""


async def evaluate_answer(
    submission: ExerciseSubmission,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> ExerciseEvaluation:
    """Score a user answer against the correct answer using LLM."""
    result = await db.execute(
        select(Exercise).where(Exercise.id == submission.exercise_id)
    )
    exercise = result.scalar_one_or_none()
    if exercise is None:
        raise ValueError(f"Exercise {submission.exercise_id} not found")

    # Ensure user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(
            id=user_id,
            display_name="Guest User",
            native_language="en",
        )
        db.add(user)
        await db.flush()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Correct answer: {exercise.correct_answer}\n"
                f"User's answer: {submission.user_answer}\n"
                f"Exercise type: {exercise.exercise_type}\n"
                f"Question: {exercise.question}\n"
                f"Hint: {exercise.hint or 'none'}"
            ),
        },
    ]
    data = await chat_completion_json(messages, temperature=0.2)
    evaluation = ExerciseEvaluation(
        is_correct=data.get("is_correct", False),
        score=data.get("score", 0.0),
        feedback=data.get("feedback", ""),
        correct_answer=exercise.correct_answer,
    )

    db.add(ExerciseAttempt(
        exercise_id=exercise.id,
        user_id=user_id,
        user_answer=submission.user_answer,
        is_correct=evaluation.is_correct,
        llm_feedback=evaluation.feedback,
        score=evaluation.score,
    ))
    await db.flush()
    return evaluation
