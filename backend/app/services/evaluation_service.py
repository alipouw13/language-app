"""
Exercise evaluation service.

Sends a user's answer plus the correct answer to the LLM for nuanced scoring
and feedback, then records the attempt in the Fabric OneLake Lakehouse store.

An exact (normalized) match short-circuits the LLM entirely so obviously-correct
answers grade instantly, and the score write is backgrounded to keep the
response fast.
"""

from __future__ import annotations

import re
import unicodedata

from app.models.pydantic_models import ExerciseEvaluation, ExerciseSubmission
from app.repository import store
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


def _normalize(text: str) -> str:
    """Lowercase, strip accents/punctuation and collapse whitespace for matching."""
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


async def evaluate_answer(
    submission: ExerciseSubmission, user_id: str
) -> ExerciseEvaluation:
    exercise = await store.get_exercise(submission.exercise_id)
    if exercise is None:
        raise ValueError(f"Exercise {submission.exercise_id} not found")

    correct_answer = exercise["correct_answer"]

    # Fast path: an exact (accent/case/punctuation-insensitive) match is
    # unambiguously correct, so skip the LLM round-trip entirely.
    user_norm = _normalize(submission.user_answer)
    if user_norm and user_norm == _normalize(correct_answer):
        evaluation = ExerciseEvaluation(
            is_correct=True,
            score=1.0,
            feedback="¡Correcto!",
            correct_answer=correct_answer,
        )
    else:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Correct answer: {correct_answer}\n"
                    f"User's answer: {submission.user_answer}\n"
                    f"Exercise type: {exercise['exercise_type']}\n"
                    f"Question: {exercise['question']}\n"
                    f"Hint: {exercise.get('hint') or 'none'}"
                ),
            },
        ]
        data = await chat_completion_json(
            messages, temperature=0.2, max_tokens=512, reasoning_effort="minimal"
        )
        evaluation = ExerciseEvaluation(
            is_correct=bool(data.get("is_correct", False)),
            score=float(data.get("score", 0.0)),
            feedback=data.get("feedback", ""),
            correct_answer=correct_answer,
        )

    # Persist the attempt off the critical path — the response returns immediately.
    await store.record_exercise_score(
        exercise_id=exercise["id"],
        user_id=user_id,
        user_answer=submission.user_answer,
        is_correct=evaluation.is_correct,
        score=evaluation.score,
        feedback=evaluation.feedback,
        background=True,
    )
    return evaluation
