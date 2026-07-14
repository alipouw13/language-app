"""
Entity store backed by Delta tables in the Fabric OneLake Lakehouse.

This module is the single persistence boundary for the application. Services
call these async helpers instead of an ORM; rows are plain ``dict`` objects.

Tables (Delta):
    users, lessons, exercises, exercise_scores, conversations, conversation_turns,
    worksheet_submissions, worksheet_responses, date_dim
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from app.repository.lakehouse import get_lakehouse

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #
USERS = "users"
LESSONS = "lessons"
EXERCISES = "exercises"
EXERCISE_SCORES = "exercise_scores"
CONVERSATIONS = "conversations"
CONVERSATION_TURNS = "conversation_turns"
WORKSHEET_SUBMISSIONS = "worksheet_submissions"
WORKSHEET_RESPONSES = "worksheet_responses"
DATE_DIM = "date_dim"

# Calendar dimension is built contiguously from this date forward (for Power BI).
_DATE_DIM_START = date(2024, 1, 1)

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
        ("news_id", pa.string()),           # nullable — RTI news item this chat is grounded in
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
    # Worksheet submission header (one row per submitted worksheet).
    WORKSHEET_SUBMISSIONS: pa.schema([
        ("submission_id", pa.string()),
        ("lesson_id", pa.string()),
        ("user_id", pa.string()),
        ("target_language", pa.string()),
        ("mode", pa.string()),
        ("verb", pa.string()),
        ("scenario", pa.string()),
        ("difficulty", pa.string()),
        ("grammar_focus", pa.string()),
        ("total_exercises", pa.int64()),
        ("answered_count", pa.int64()),
        ("first_correct_count", pa.int64()),
        ("final_correct_count", pa.int64()),
        ("first_score_avg", pa.float64()),
        ("final_score_avg", pa.float64()),
        ("submitted_at", pa.string()),
        ("date_key", pa.int64()),
    ]),
    # Worksheet response detail (one row per exercise within a submission).
    WORKSHEET_RESPONSES: pa.schema([
        ("response_id", pa.string()),
        ("submission_id", pa.string()),
        ("lesson_id", pa.string()),
        ("user_id", pa.string()),
        ("exercise_id", pa.string()),
        ("order_index", pa.int64()),
        ("exercise_type", pa.string()),
        ("question", pa.string()),
        ("correct_answer", pa.string()),
        ("user_answer", pa.string()),
        ("first_score", pa.float64()),       # nullable
        ("first_is_correct", pa.bool_()),    # nullable
        ("final_score", pa.float64()),       # nullable
        ("final_is_correct", pa.bool_()),    # nullable
        ("attempts", pa.int64()),
        ("feedback", pa.string()),           # nullable
        ("target_language", pa.string()),
        ("difficulty", pa.string()),
        ("mode", pa.string()),
        ("submitted_at", pa.string()),
        ("date_key", pa.int64()),
    ]),
    # Calendar dimension for Power BI (Direct Lake / DirectQuery).
    DATE_DIM: pa.schema([
        ("date_key", pa.int64()),            # yyyymmdd
        ("date", pa.string()),               # yyyy-mm-dd
        ("year", pa.int64()),
        ("quarter", pa.int64()),
        ("month", pa.int64()),
        ("month_name", pa.string()),
        ("month_year", pa.string()),         # e.g. "2026-06"
        ("day", pa.int64()),
        ("day_of_week", pa.int64()),         # 1=Mon … 7=Sun
        ("day_name", pa.string()),
        ("week_of_year", pa.int64()),
        ("is_weekend", pa.bool_()),
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
# In-process caches                                                            #
# --------------------------------------------------------------------------- #
# Exercises are immutable once created, so caching them per-process removes a
# full-table OneLake scan from the hot grading path (every "Check" click). Known
# user ids are cached the same way so repeat requests skip the users scan.
_exercise_cache: dict[str, dict[str, Any]] = {}
_known_user_ids: set[str] = set()

# Fire-and-forget background writes (e.g. per-exercise scores) are kept off the
# request's critical path. We hold references so tasks aren't garbage-collected.
_bg_tasks: set[Any] = set()


def _cache_exercise(row: dict[str, Any]) -> None:
    eid = row.get("id")
    if eid:
        _exercise_cache[eid] = dict(row)


def _spawn_bg(coro) -> None:
    """Schedule *coro* to run detached from the caller; log any failure."""
    import asyncio

    async def _runner() -> None:
        try:
            await coro
        except Exception:  # noqa: BLE001
            logger.exception("Background store write failed")

    task = asyncio.create_task(_runner())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


# --------------------------------------------------------------------------- #
# Startup                                                                      #
# --------------------------------------------------------------------------- #
async def ensure_ready() -> dict[str, Any]:
    """Verify the lakehouse backend is reachable (called at startup)."""
    return await get_lakehouse().health_check()


async def table_status() -> list[dict[str, Any]]:
    """Per-table existence + row count, for confirming the lakehouse state."""
    lake = get_lakehouse()
    status: list[dict[str, Any]] = []
    for table, schema in _SCHEMAS.items():
        try:
            rows = await lake.read_all(table, schema)
            status.append({"table": table, "exists": True, "rows": len(rows)})
        except Exception as exc:  # noqa: BLE001
            status.append(
                {"table": table, "exists": False, "rows": 0, "error": str(exc)[:200]}
            )
    return status


async def ensure_tables() -> dict[str, list[str]]:
    """Create every Delta table (empty, with schema) if it doesn't yet exist.

    Called at startup so the lakehouse shows all tables immediately — before any
    worksheet is generated or submitted — ready to be populated. Idempotent.
    The calendar dimension is also seeded so date-based Power BI models work.
    """
    lake = get_lakehouse()
    created: list[str] = []
    existed: list[str] = []
    failed: list[str] = []
    last_error: str | None = None
    for table, schema in _SCHEMAS.items():
        try:
            was_created = await lake.create_table(table, schema)
            (created if was_created else existed).append(table)
        except Exception as exc:  # noqa: BLE001
            failed.append(table)
            last_error = str(exc)
            logger.warning("Could not ensure table %s: %s", table, str(exc)[:200])

    if failed and not created and not existed:
        # Every table failed — almost always a storage-connectivity problem.
        logger.error(
            "Could not provision ANY lakehouse tables — the storage backend looks "
            "unreachable. Last error: %s",
            (last_error or "")[:300],
        )
        return {"created": created, "existed": existed, "failed": failed}

    # Seed the calendar dimension if it's empty (it was just created).
    try:
        await ensure_date_dim()
    except Exception:
        logger.exception("Failed to seed date_dim")

    if created:
        logger.info("Created lakehouse tables: %s", ", ".join(created))
    logger.info(
        "Lakehouse tables ready (%d ok, %d failed)",
        len(created) + len(existed),
        len(failed),
    )
    return {"created": created, "existed": existed, "failed": failed}


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
    # Fast path: a user id we've already confirmed/created this process.
    if user_id and user_id in _known_user_ids:
        return user_id

    lake = get_lakehouse()
    schema = _schema(USERS)
    users = await lake.read_all(USERS, schema)

    if user_id:
        if any(u["id"] == user_id for u in users):
            _known_user_ids.add(user_id)
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
        _known_user_ids.add(user_id)
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
    _known_user_ids.add(new_id)
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
        for row in exercise_rows:
            _cache_exercise(row)

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


async def get_lessons_by_ids(lesson_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch several lessons in a single table scan.

    Returns a mapping of ``lesson_id -> lesson`` (with a parsed ``worksheet``).
    Unlike :func:`get_lesson`, exercises are **not** attached, so callers that
    only need the worksheet content (e.g. export) avoid a second full-table
    scan per lesson. Ids with no matching lesson are simply absent.
    """
    if not lesson_ids:
        return {}
    wanted = set(lesson_ids)
    lake = get_lakehouse()
    lessons = await lake.read_all(LESSONS, _schema(LESSONS))
    out: dict[str, dict[str, Any]] = {}
    for l in lessons:
        if l["id"] in wanted:
            row = dict(l)
            row["worksheet"] = json.loads(row.pop("worksheet_json"))
            out[l["id"]] = row
    return out


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
    for row in rows:
        _cache_exercise(row)
    rows = [e for e in rows if e["lesson_id"] == lesson_id]
    rows.sort(key=lambda e: e["order_index"])
    return rows


async def get_exercise(exercise_id: str) -> dict[str, Any] | None:
    # Exercises are immutable — serve from the in-process cache when present to
    # avoid a full-table OneLake scan on every grading request.
    cached = _exercise_cache.get(exercise_id)
    if cached is not None:
        return dict(cached)
    lake = get_lakehouse()
    rows = await lake.read_all(EXERCISES, _schema(EXERCISES))
    for row in rows:
        _cache_exercise(row)
    return next((dict(e) for e in rows if e["id"] == exercise_id), None)


async def record_exercise_score(
    *,
    exercise_id: str,
    user_id: str,
    user_answer: str,
    is_correct: bool,
    score: float,
    feedback: str,
    background: bool = False,
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
    if background:
        # Keep the OneLake append off the request's critical path; the score is
        # still persisted for reporting, just not awaited by the HTTP response.
        _spawn_bg(lake.append(EXERCISE_SCORES, [row], _schema(EXERCISE_SCORES)))
        return
    await lake.append(EXERCISE_SCORES, [row], _schema(EXERCISE_SCORES))


# --------------------------------------------------------------------------- #
# Conversations + turns                                                        #
# --------------------------------------------------------------------------- #
async def create_conversation(
    *, user_id: str, target_language: str, scenario_context: str | None,
    news_id: str | None = None,
) -> dict[str, Any]:
    lake = get_lakehouse()
    conv = _coerce(
        {
            "id": _new_id(),
            "user_id": user_id,
            "target_language": target_language,
            "scenario_context": scenario_context,
            "news_id": news_id,
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


# --------------------------------------------------------------------------- #
# Date dimension (Power BI calendar)                                           #
# --------------------------------------------------------------------------- #
_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _date_row(d: date) -> dict[str, Any]:
    iso_year, iso_week, iso_weekday = d.isocalendar()
    return {
        "date_key": int(d.strftime("%Y%m%d")),
        "date": d.isoformat(),
        "year": d.year,
        "quarter": (d.month - 1) // 3 + 1,
        "month": d.month,
        "month_name": _MONTHS[d.month - 1],
        "month_year": d.strftime("%Y-%m"),
        "day": d.day,
        "day_of_week": iso_weekday,            # 1=Mon … 7=Sun
        "day_name": _DAYS[iso_weekday - 1],
        "week_of_year": int(iso_week),
        "is_weekend": iso_weekday >= 6,
    }


async def ensure_date_dim(through: date | None = None) -> None:
    """Ensure the calendar dimension covers up to ``through`` (default: today).

    Rebuilds a contiguous table from ``_DATE_DIM_START`` to one year beyond the
    needed end date, but only when the existing table doesn't already reach it.
    """
    lake = get_lakehouse()
    schema = _schema(DATE_DIM)
    target = max(through or date.today(), date.today())
    needed_key = int(target.strftime("%Y%m%d"))

    existing = await lake.read_all(DATE_DIM, schema)
    if existing:
        current_max = max(r["date_key"] for r in existing)
        if current_max >= needed_key:
            return

    end = date(target.year + 1, 12, 31)
    rows: list[dict[str, Any]] = []
    d = _DATE_DIM_START
    while d <= end:
        rows.append(_date_row(d))
        d += timedelta(days=1)
    await lake.overwrite(DATE_DIM, rows, schema)


# --------------------------------------------------------------------------- #
# Worksheet submissions                                                        #
# --------------------------------------------------------------------------- #
async def create_worksheet_submission(
    *,
    user_id: str,
    lesson: dict[str, Any],
    responses: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist a worksheet submission header + per-exercise response rows.

    ``responses`` is the fully-resolved list (correct answers, first/final
    scores, attempts, feedback) produced by the submission service. Returns the
    submission summary header.
    """
    lake = get_lakehouse()
    submission_id = _new_id()
    now_dt = datetime.now(timezone.utc)
    submitted_at = now_dt.isoformat()
    submitted_date = now_dt.date()
    date_key = int(submitted_date.strftime("%Y%m%d"))

    target_language = lesson["target_language"]
    difficulty = lesson["difficulty"]
    mode = lesson.get("mode") or "scenario"

    answered = [r for r in responses if (r.get("user_answer") or "").strip()]
    first_scores = [r["first_score"] for r in answered if r.get("first_score") is not None]
    final_scores = [r["final_score"] for r in answered if r.get("final_score") is not None]
    first_correct = sum(1 for r in answered if r.get("first_is_correct"))
    final_correct = sum(1 for r in answered if r.get("final_is_correct"))

    header = _coerce(
        {
            "submission_id": submission_id,
            "lesson_id": lesson["id"],
            "user_id": user_id,
            "target_language": target_language,
            "mode": mode,
            "verb": lesson.get("verb"),
            "scenario": lesson.get("scenario"),
            "difficulty": difficulty,
            "grammar_focus": lesson.get("grammar_focus"),
            "total_exercises": len(responses),
            "answered_count": len(answered),
            "first_correct_count": first_correct,
            "final_correct_count": final_correct,
            "first_score_avg": round(sum(first_scores) / len(first_scores), 4) if first_scores else 0.0,
            "final_score_avg": round(sum(final_scores) / len(final_scores), 4) if final_scores else 0.0,
            "submitted_at": submitted_at,
            "date_key": date_key,
        },
        _schema(WORKSHEET_SUBMISSIONS),
    )
    await lake.append(WORKSHEET_SUBMISSIONS, [header], _schema(WORKSHEET_SUBMISSIONS))

    detail_rows = [
        _coerce(
            {
                "response_id": _new_id(),
                "submission_id": submission_id,
                "lesson_id": lesson["id"],
                "user_id": user_id,
                "exercise_id": r.get("exercise_id"),
                "order_index": r.get("order_index", 0),
                "exercise_type": r.get("exercise_type", ""),
                "question": r.get("question", ""),
                "correct_answer": r.get("correct_answer", ""),
                "user_answer": r.get("user_answer", "") or "",
                "first_score": r.get("first_score"),
                "first_is_correct": r.get("first_is_correct"),
                "final_score": r.get("final_score"),
                "final_is_correct": r.get("final_is_correct"),
                "attempts": int(r.get("attempts", 0) or 0),
                "feedback": r.get("feedback"),
                "target_language": target_language,
                "difficulty": difficulty,
                "mode": mode,
                "submitted_at": submitted_at,
                "date_key": date_key,
            },
            _schema(WORKSHEET_RESPONSES),
        )
        for r in responses
    ]
    if detail_rows:
        await lake.append(WORKSHEET_RESPONSES, detail_rows, _schema(WORKSHEET_RESPONSES))

    await ensure_date_dim(submitted_date)

    return {
        "submission_id": submission_id,
        "lesson_id": lesson["id"],
        "total_exercises": header["total_exercises"],
        "answered_count": header["answered_count"],
        "first_score_avg": header["first_score_avg"],
        "final_score_avg": header["final_score_avg"],
        "first_correct_count": first_correct,
        "final_correct_count": final_correct,
        "submitted_at": submitted_at,
    }


async def list_submissions(
    user_id: str | None, page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    lake = get_lakehouse()
    subs = await lake.read_all(WORKSHEET_SUBMISSIONS, _schema(WORKSHEET_SUBMISSIONS))
    if user_id:
        subs = [s for s in subs if s["user_id"] == user_id]
    subs.sort(key=lambda s: s["submitted_at"], reverse=True)
    total = len(subs)
    start = (page - 1) * page_size
    return subs[start : start + page_size], total


async def get_submission(submission_id: str) -> dict[str, Any] | None:
    """Return a submission header with its per-exercise response rows."""
    lake = get_lakehouse()
    subs = await lake.read_all(WORKSHEET_SUBMISSIONS, _schema(WORKSHEET_SUBMISSIONS))
    header = next((s for s in subs if s["submission_id"] == submission_id), None)
    if header is None:
        return None
    header = dict(header)
    responses = await lake.read_all(WORKSHEET_RESPONSES, _schema(WORKSHEET_RESPONSES))
    rows = [r for r in responses if r["submission_id"] == submission_id]
    rows.sort(key=lambda r: r["order_index"])
    header["responses"] = rows
    return header
