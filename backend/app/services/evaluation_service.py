"""
Exercise evaluation service.

Sends a user's answer to the LLM for nuanced scoring and feedback, then records
the attempt in the Fabric OneLake Lakehouse store.

Grading is exercise-type aware:

* Closed exercises (fill_blank, conjugation, translation) are graded against the
  stored correct answer, accepting valid equivalents.
* Open-ended sentence-building is graded on STRUCTURE and grammar (does it use
  the required verb/expression in the requested tense?), NOT on matching the
  specific content of the example answer. The learner is free to write about any
  subject, person or situation.

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

# Open-ended production tasks: the learner writes their OWN sentence, so there is
# no single correct answer. These are graded on structure/grammar, not on
# matching the specific content (subjects, people, places) of the example.
OPEN_ENDED_TYPES = {"sentence_building"}

# Closed exercises (fill_blank, conjugation, translation) have a target answer /
# meaning, so we grade against the stored correct answer while accepting valid
# equivalents.
CLOSED_SYSTEM_PROMPT = """\
You are a language-learning exercise evaluator.
Given a correct answer and a user's attempt, respond with a JSON object:
{
  "is_correct": true/false,
  "score": 0.0 to 1.0,
  "feedback": "brief explanation of what was right/wrong"
}
Be encouraging. If almost correct, give partial credit.
Ignore case and punctuation differences when evaluating.
Accept equivalent answers (e.g., synonyms, different valid conjugations, or an
equally valid alternative translation that preserves the meaning).
Return ONLY valid JSON."""

# Open-ended sentence building: judge the STRUCTURE, not the specific content.
OPEN_ENDED_SYSTEM_PROMPT = """\
You are a supportive language-learning evaluator for OPEN-ENDED sentence-building
tasks. The learner must construct their OWN natural sentence that satisfies the
task's structural requirements (for example: a target verb or expression used in
a specific tense). There is NO single correct answer.

Grade ONLY on:
1. Structure - does the sentence use the required verb/expression in the
   requested tense/grammar (as stated in the question and hint)?
2. Correctness - is it grammatically correct and natural in the target language?
3. Constraints - does it satisfy any explicit constraint in the question/hint?

Do NOT penalize the learner for:
- choosing different subjects, people, objects, places or situations than the
  example answer,
- expressing a different meaning, as long as the structural requirements are met.
The "example answer" provided is ONE valid possibility among many; it is NOT a
target the learner must reproduce. Never require the learner's content to match it.

Treat minor issues (a missing accent, a small typo) as a small deduction with
partial credit, never as a failure. If the required structure is present and the
sentence is grammatical, it should score highly (>= 0.9) even if it differs
completely in content from the example.

Respond with a JSON object:
{
  "is_correct": true/false,
  "score": 0.0 to 1.0,
  "feedback": "brief, encouraging explanation focused on structure and grammar"
}
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
    exercise_type = exercise.get("exercise_type") or ""
    is_open_ended = exercise_type in OPEN_ENDED_TYPES

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
        if is_open_ended:
            system_prompt = OPEN_ENDED_SYSTEM_PROMPT
            reference_label = "Example answer (one of many valid, do NOT require a match)"
        else:
            system_prompt = CLOSED_SYSTEM_PROMPT
            reference_label = "Correct answer"
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"{reference_label}: {correct_answer}\n"
                    f"User's answer: {submission.user_answer}\n"
                    f"Exercise type: {exercise_type}\n"
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
