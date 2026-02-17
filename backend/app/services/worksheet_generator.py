"""
Worksheet generation service.

Builds a structured prompt, calls the LLM in strict JSON mode,
validates the response, and persists the resulting lesson.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Exercise, Lesson, User
from app.models.pydantic_models import WorksheetRequest, WorksheetResponse
from app.services.llm_service import chat_completion_json

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"en": "English", "fr": "French", "es": "Spanish"}

SYSTEM_PROMPT = """\
You are an expert language teacher and curriculum designer.
Generate a structured worksheet as a SINGLE JSON object.

The JSON MUST contain exactly these keys:
- scenario_summary (string): 2-3 sentence overview of the scenario
- vocabulary (array of objects with word, translation, example_sentence)
- grammar_focus (string): the primary grammar topic covered (MUST match the requested verb tense/grammar if provided)
- explanations (string): clear, beginner-friendly grammar explanation focusing on the specified tense/grammar topic
- exercises (array of objects with type, question, answer, hint)
  type must be one of: fill_blank, conjugation, sentence_building, translation
- roleplay_prompts (array of strings): 3-5 conversation starters for practice

IMPORTANT: If a specific verb tense or grammar topic is requested, ALL exercises MUST focus on that tense.
The explanations MUST thoroughly cover the requested grammar topic with conjugation tables if applicable.
Include 8-12 vocabulary items and 6-10 exercises.
Return ONLY valid JSON. No markdown, no code fences."""


def _build_user_prompt(req: WorksheetRequest) -> str:
    lang = LANGUAGE_NAMES.get(req.target_language, req.target_language)
    parts = [
        f"Create a {lang} language worksheet for the scenario: \"{req.scenario}\".",
        f"Difficulty level: {req.difficulty} (CEFR).",
    ]
    if req.grammar_focus:
        parts.append(f"REQUIRED GRAMMAR FOCUS: {req.grammar_focus}. All exercises must practice this specific tense/grammar topic.")
    parts.append("Ensure exercises test both comprehension and production.")
    return " ".join(parts)


async def generate_worksheet(req: WorksheetRequest) -> WorksheetResponse:
    """Generate a worksheet via LLM and return the validated response."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(req)},
    ]
    data = await chat_completion_json(messages, temperature=0.4, max_tokens=4096)
    return WorksheetResponse(**data)


async def generate_and_persist(
    req: WorksheetRequest,
    db: AsyncSession,
) -> tuple[uuid.UUID, WorksheetResponse]:
    """Generate a worksheet, store the lesson and its exercises, return both."""
    worksheet = await generate_worksheet(req)

    user_id = req.user_id or uuid.uuid4()

    # Ensure user exists (create default user if needed)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=user_id,
            display_name="Guest User",
            native_language="en",
        )
        db.add(user)
        await db.flush()

    lesson = Lesson(
        user_id=user_id,
        target_language=req.target_language,
        scenario=req.scenario,
        grammar_focus=req.grammar_focus,
        difficulty=req.difficulty,
        worksheet_json=worksheet.model_dump(),
    )
    db.add(lesson)
    await db.flush()  # get lesson.id

    exercise_ids: list[uuid.UUID] = []
    for idx, ex in enumerate(worksheet.exercises):
        db_exercise = Exercise(
            lesson_id=lesson.id,
            exercise_type=ex.type,
            question=ex.question,
            correct_answer=ex.answer,
            hint=ex.hint,
            order_index=idx,
        )
        db.add(db_exercise)
        await db.flush()  # get exercise.id
        exercise_ids.append(db_exercise.id)

    return lesson.id, worksheet, exercise_ids
