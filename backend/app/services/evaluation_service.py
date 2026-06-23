"""
Exercise evaluation service.

Sends a user's answer plus the correct answer to the LLM for nuanced scoring
and feedback, then records the attempt in the Fabric OneLake Lakehouse store.
"""

from __future__ import annotations

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


async def evaluate_answer(
    submission: ExerciseSubmission, user_id: str
) -> ExerciseEvaluation:
    exercise = await store.get_exercise(submission.exercise_id)
    if exercise is None:
        raise ValueError(f"Exercise {submission.exercise_id} not found")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Correct answer: {exercise['correct_answer']}\n"
                f"User's answer: {submission.user_answer}\n"
                f"Exercise type: {exercise['exercise_type']}\n"
                f"Question: {exercise['question']}\n"
                f"Hint: {exercise.get('hint') or 'none'}"
            ),
        },
    ]
    data = await chat_completion_json(messages, temperature=0.2)
    evaluation = ExerciseEvaluation(
        is_correct=bool(data.get("is_correct", False)),
        score=float(data.get("score", 0.0)),
        feedback=data.get("feedback", ""),
        correct_answer=exercise["correct_answer"],
    )

    await store.record_exercise_score(
        exercise_id=exercise["id"],
        user_id=user_id,
        user_answer=submission.user_answer,
        is_correct=evaluation.is_correct,
        score=evaluation.score,
        feedback=evaluation.feedback,
    )
    return evaluation
