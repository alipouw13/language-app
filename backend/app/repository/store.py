"""
Entity store backed by Delta tables in the Fabric OneLake Lakehouse.

This module is the single persistence boundary for the application. Services
call these async helpers instead of an ORM; rows are plain ``dict`` objects.

Tables (Delta):
    users, lessons, exercises, exercise_scores, conversations, conversation_turns
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import pyarrow as pa

from app.repository.lakehouse import get_lakehouse

# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #
USERS = "users"
LESSONS = "lessons"
EXERCISES = "exercises"
EXERCISE_SCORES = "exercise_scores"
CONVERSATIONS = "conversations"
CONVERSATION_TURNS = "conversation_turns"

_SCHEMAS: dict[str, pa.Schema] = {
    USERS: pa.schema([
        ("id", pa.string()),
        ("display_name", pa.string()),
        ("native_language", pa.string()),
        ("created_at", pa.string()),
    ]),
    LESSONS: pa.schema([
        ("id", pa.string()),
        ("user_id", pa.string()),
        ("target_language", pa.string()),
        ("scenario", pa.string()),
        ("mode", pa.string()),            # "scenario" | "verb"
        ("verb", pa.string()),            # nullable
        ("grammar_focus", pa.string()),   # nullable
        ("difficulty", pa.string()),
        ("worksheet_json", pa.string()),
        ("version", pa.int64()),
        ("created_at", pa.string()),
    ]),
    EXERCISES: pa.schema([
        ("id", pa.string()),
        ("lesson_id", pa.string()),
        ("order_index", pa.int64()),
        ("exercise_type", pa.string()),
        ("question", pa.string()),
        ("correct_answer", pa.string()),
        ("hint", pa.string()),            # nullable
    ]),
    EXERCISE_SCORES: pa.schema([
        ("id", pa.string()),
        ("exercise_id", pa.string()),
        ("user_id", pa.string()),
        ("user_answer", pa.string()),
        ("is_correct", pa.bool_()),
        ("score", pa.float64()),
        ("feedback", pa.string()),
        ("created_at", pa.string()),
    ]),
    CONVERSATIONS: pa.schema([
        ("id", pa.string()),
        ("user_id", pa.string()),
        ("target_language", pa.string()),
        ("scenario_context", pa.string()),  # nullable
        ("created_at", pa.string()),
        ("ended_at", pa.string()),          # nullable
    ]),
    CONVERSATION_TURNS: pa.schema([
        ("id", pa.string()),
        ("conversation_id", pa.string()),
        ("role", pa.string()),
        ("text", pa.string()),
        ("corrected_text", pa.string()),    # nullable
        ("turn_index", pa.int64()),
        ("created_at", pa.string()),
    ]),
}


def _schema(table: str) -> pa.Schema:
    return _SCHEMAS[table]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _coerce(row: dict[str, Any], schema: pa.Schema) -> dict[str, Any]:
    """Ensure a row has every schema field (missing → None)."""
    return {field.name: row.get(field.name) for field in schema}


# --------------------------------------------------------------------------- #
# Startup                                                                      #
# --------------------------------------------------------------------------- #
async def ensure_ready() -> dict[str, Any]:
    """Verify the lakehouse backend is reachable (called at startup)."""
    return await get_lakehouse().health_check()


# --------------------------------------------------------------------------- #
# Users                                                                        #
# --------------------------------------------------------------------------- #
async def get_or_create_user(
    user_id: str | None,
    *,
    display_name: str = "Learner",
    native_language: str = "en",
) -> str:
    """Return an existing user id or create a new user, returning its id."""
    lake = get_lakehouse()
    schema = _schema(USERS)
    users = await lake.read_all(USERS, schema)

    if user_id:
        if any(u["id"] == user_id for u in users):
            return user_id
        row = _coerce(
            {
                "id": user_id,
                "display_name": display_name,
                "native_language": native_language,
                "created_at": _now(),
            },
            schema,
        )
        await lake.append(USERS, [row], schema)
        return user_id

    new_id = _new_id()
    row = _coerce(
        {
            "id": new_id,
            "display_name": display_name,
            "native_language": native_language,
            "created_at": _now(),
        },
        schema,
    )
    await lake.append(USERS, [row], schema)
    return new_id


# --------------------------------------------------------------------------- #
# Lessons + exercises                                                          #
# --------------------------------------------------------------------------- #
async def create_lesson(
    *,
    user_id: str,
    target_language: str,
    scenario: str,
    difficulty: str,
    worksheet: dict[str, Any],
    mode: str = "scenario",
    verb: str | None = None,
    grammar_focus: str | None = None,
    exercises: list[dict[str, Any]] | None = None,
) -> tuple[str, list[str]]:
    """Persist a lesson and its exercises; return (lesson_id, exercise_ids)."""
    lake = get_lakehouse()
    lesson_id = _new_id()

    lesson_row = _coerce(
        {
            "id": lesson_id,
            "user_id": user_id,
            "target_language": target_language,
            "scenario": scenario,
            "mode": mode,
            "verb": verb,
            "grammar_focus": grammar_focus,
            "difficulty": difficulty,
            "worksheet_json": json.dumps(worksheet, ensure_ascii=False),
            "version": 1,
            "created_at": _now(),
        },
        _schema(LESSONS),
    )
    await lake.append(LESSONS, [lesson_row], _schema(LESSONS))

    exercise_ids: list[str] = []
    exercise_rows: list[dict[str, Any]] = []
    for idx, ex in enumerate(exercises or []):
        eid = _new_id()
        exercise_ids.append(eid)
        exercise_rows.append(
            _coerce(
                {
                    "id": eid,
                    "lesson_id": lesson_id,
                    "order_index": idx,
                    "exercise_type": ex.get("type", ""),
                    "question": ex.get("question", ""),
                    "correct_answer": ex.get("answer", ""),
                    "hint": ex.get("hint") or None,
                },
                _schema(EXERCISES),
            )
        )
    if exercise_rows:
        await lake.append(EXERCISES, exercise_rows, _schema(EXERCISES))

    return lesson_id, exercise_ids


async def get_lesson(lesson_id: str) -> dict[str, Any] | None:
    lake = get_lakehouse()
    lessons = await lake.read_all(LESSONS, _schema(LESSONS))
    lesson = next((l for l in lessons if l["id"] == lesson_id), None)
    if lesson is None:
        return None
    lesson = dict(lesson)
    lesson["worksheet"] = json.loads(lesson.pop("worksheet_json"))
    lesson["exercises"] = await list_exercises_by_lesson(lesson_id)
    return lesson


async def list_lessons(
    user_id: str | None, page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    lake = get_lakehouse()
    lessons = await lake.read_all(LESSONS, _schema(LESSONS))
    if user_id:
        lessons = [l for l in lessons if l["user_id"] == user_id]
    lessons.sort(key=lambda l: l["created_at"], reverse=True)
    total = len(lessons)
    start = (page - 1) * page_size
    page_items = lessons[start : start + page_size]

    items: list[dict[str, Any]] = []
    for l in page_items:
        worksheet = json.loads(l["worksheet_json"])
        items.append(
            {
                "id": l["id"],
                "scenario": l["scenario"],
                "target_language": l["target_language"],
                "difficulty": l["difficulty"],
                "mode": l.get("mode") or "scenario",
                "verb": l.get("verb"),
                "exercise_count": len(worksheet.get("exercises", [])),
                "created_at": l["created_at"],
            }
        )
    return items, total


async def list_exercises_by_lesson(lesson_id: str) -> list[dict[str, Any]]:
    lake = get_lakehouse()
    rows = await lake.read_all(EXERCISES, _schema(EXERCISES))
    rows = [e for e in rows if e["lesson_id"] == lesson_id]
    rows.sort(key=lambda e: e["order_index"])
    return rows


async def get_exercise(exercise_id: str) -> dict[str, Any] | None:
    lake = get_lakehouse()
    rows = await lake.read_all(EXERCISES, _schema(EXERCISES))
    return next((e for e in rows if e["id"] == exercise_id), None)


async def record_exercise_score(
    *,
    exercise_id: str,
    user_id: str,
    user_answer: str,
    is_correct: bool,
    score: float,
    feedback: str,
) -> None:
    lake = get_lakehouse()
    row = _coerce(
        {
            "id": _new_id(),
            "exercise_id": exercise_id,
            "user_id": user_id,
            "user_answer": user_answer,
            "is_correct": bool(is_correct),
            "score": float(score),
            "feedback": feedback,
            "created_at": _now(),
        },
        _schema(EXERCISE_SCORES),
    )
    await lake.append(EXERCISE_SCORES, [row], _schema(EXERCISE_SCORES))


# --------------------------------------------------------------------------- #
# Conversations + turns                                                        #
# --------------------------------------------------------------------------- #
async def create_conversation(
    *, user_id: str, target_language: str, scenario_context: str | None
) -> dict[str, Any]:
    lake = get_lakehouse()
    conv = _coerce(
        {
            "id": _new_id(),
            "user_id": user_id,
            "target_language": target_language,
            "scenario_context": scenario_context,
            "created_at": _now(),
            "ended_at": None,
        },
        _schema(CONVERSATIONS),
    )
    await lake.append(CONVERSATIONS, [conv], _schema(CONVERSATIONS))
    return conv


async def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    lake = get_lakehouse()
    convos = await lake.read_all(CONVERSATIONS, _schema(CONVERSATIONS))
    conv = next((c for c in convos if c["id"] == conversation_id), None)
    if conv is None:
        return None
    conv = dict(conv)
    conv["turns"] = await list_turns(conversation_id)
    return conv


async def list_turns(conversation_id: str) -> list[dict[str, Any]]:
    lake = get_lakehouse()
    rows = await lake.read_all(CONVERSATION_TURNS, _schema(CONVERSATION_TURNS))
    rows = [t for t in rows if t["conversation_id"] == conversation_id]
    rows.sort(key=lambda t: t["turn_index"])
    return rows


async def append_turn(
    *,
    conversation_id: str,
    role: str,
    text: str,
    turn_index: int,
    corrected_text: str | None = None,
) -> dict[str, Any]:
    lake = get_lakehouse()
    row = _coerce(
        {
            "id": _new_id(),
            "conversation_id": conversation_id,
            "role": role,
            "text": text,
            "corrected_text": corrected_text,
            "turn_index": turn_index,
            "created_at": _now(),
        },
        _schema(CONVERSATION_TURNS),
    )
    await lake.append(CONVERSATION_TURNS, [row], _schema(CONVERSATION_TURNS))
    return row


async def list_conversations(
    user_id: str | None, page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    lake = get_lakehouse()
    convos = await lake.read_all(CONVERSATIONS, _schema(CONVERSATIONS))
    if user_id:
        convos = [c for c in convos if c["user_id"] == user_id]
    convos.sort(key=lambda c: c["created_at"], reverse=True)
    total = len(convos)
    start = (page - 1) * page_size
    page_items = convos[start : start + page_size]

    turns = await lake.read_all(CONVERSATION_TURNS, _schema(CONVERSATION_TURNS))
    counts: dict[str, int] = {}
    for t in turns:
        counts[t["conversation_id"]] = counts.get(t["conversation_id"], 0) + 1

    items = [
        {
            "id": c["id"],
            "target_language": c["target_language"],
            "scenario_context": c["scenario_context"],
            "turn_count": counts.get(c["id"], 0),
            "created_at": c["created_at"],
        }
        for c in page_items
    ]
    return items, total
