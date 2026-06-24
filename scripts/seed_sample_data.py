"""Seed realistic sample data into the Lakehouse Delta tables (dbo schema).

Writes through the app's own ``store``/``lakehouse`` layer, so it always lands in
the configured backend and schema (``ONELAKE_SCHEMA``, e.g. ``dbo``) using the
authoritative pyarrow ``_SCHEMAS`` — no risk of a divergent/"bad" schema.

Generates:
  * users            — N sample users named "Sample User 1..N" (dimension).
  * lessons          — fact (each tied to a user, language, scenario/verb).
  * exercises        — line items per lesson.
  * worksheet_submissions / worksheet_responses — graded submission facts.
  * exercise_scores  — standalone "Check" scores.
  * conversations / conversation_turns — chat practice facts.
  * date_dim         — ensured to cover the generated date range.

All timestamps are spread randomly over the past ``--days`` (default 30) so the
data looks realistic for a Power BI report. Sample users get deterministic GUIDs
prefixed ``5a3b1e00`` ("sample") so the data is easy to identify or remove later
(e.g. delete rows where user_id LIKE '5a3b1e00%').

Run from the backend/ directory so backend/.env loads:

    cd backend
    python ../scripts/seed_sample_data.py --dry-run      # validate, no writes
    python ../scripts/seed_sample_data.py                # seed configured backend
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

# Allow running from repo root or backend/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, "backend")
sys.path.insert(0, ".")

import pyarrow as pa  # noqa: E402

from app.repository import store  # noqa: E402
from app.repository.lakehouse import get_lakehouse  # noqa: E402

# Windows consoles default to cp1252; emit UTF-8 so status lines never crash.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

# --------------------------------------------------------------------------- #
# Content pools (kept lightweight; values mirror what the app produces)        #
# --------------------------------------------------------------------------- #
SAMPLE_PREFIX = "5a3b1e00-0000-4000-8000-"  # deterministic sample-user GUID stem

LANGUAGES = ["es", "es", "es", "fr", "fr", "fr", "en"]  # weighted es/fr > en
LEVELS = ["A1", "A2", "A2", "B1", "B1", "B1", "B2", "B2", "C1"]
NATIVE = ["en", "en", "en", "es", "fr"]

SCENARIOS = [
    "Ordering food at a restaurant", "Booking a hotel room", "Asking for directions",
    "At the pharmacy", "A job interview", "Making small talk at a party",
    "Renting an apartment", "At the airport check-in", "Shopping for clothes",
    "Visiting the doctor", "Opening a bank account", "Planning a weekend trip",
    "Buying train tickets", "Ordering coffee", "Meeting a friend's family",
    "Negotiating at a market", "Calling customer support", "At the hair salon",
    "Discussing weekend plans", "Talking about your hobbies",
]
GRAMMAR_FOCUS = [
    "present", "preterite", "imperfect", "future", "conditional",
    "subjunctive", "present perfect", None, None,
]
VERBS = {
    "es": ["hablar", "comer", "vivir", "tener", "hacer", "ir", "ser", "estar",
            "poder", "querer", "decir", "ver", "salir", "venir", "poner"],
    "fr": ["parler", "manger", "vivre", "avoir", "faire", "aller", "être",
            "pouvoir", "vouloir", "dire", "voir", "prendre", "venir", "savoir"],
    "en": ["to speak", "to eat", "to live", "to have", "to make", "to go",
            "to be", "to want", "to say", "to see", "to take", "to come"],
}
EXERCISE_TYPES = ["fill_blank", "conjugation", "sentence_building", "translation"]
TURN_TEXT = {
    "es": ["Hola, ¿cómo estás?", "Me gustaría practicar.", "¿Qué piensas de esto?",
            "Hoy aprendí mucho.", "Gracias por la ayuda.", "¿Puedes repetir, por favor?"],
    "fr": ["Bonjour, comment ça va ?", "Je voudrais pratiquer.", "Qu'en penses-tu ?",
            "J'ai beaucoup appris.", "Merci pour ton aide.", "Peux-tu répéter ?"],
    "en": ["Hi, how are you?", "I'd like to practice.", "What do you think?",
            "I learned a lot today.", "Thanks for the help.", "Can you repeat that?"],
}
FEEDBACK = [
    "Great job!", "Almost — watch the verb ending.", "Correct, well done.",
    "Check the gender agreement.", "Good, but more natural would be different.",
    "Nice use of the past tense.", "Remember the accent mark.",
]

rng = random.Random(42)


def sample_user_id(n: int) -> str:
    return f"{SAMPLE_PREFIX}{n:012d}"


def rand_dt(now: datetime, days: int) -> datetime:
    """A random timezone-aware datetime within the past *days*, business-ish hours."""
    secs = rng.randint(0, days * 86400)
    dt = now - timedelta(seconds=secs)
    # nudge toward daytime (7:00–23:00) so it looks like real usage
    return dt.replace(hour=rng.randint(7, 22), minute=rng.randint(0, 59), second=rng.randint(0, 59))


def weighted_score() -> float:
    return rng.choices([0.0, 0.25, 0.5, 0.75, 1.0], weights=[6, 10, 18, 26, 40])[0]


def date_key(d: date) -> int:
    return int(d.strftime("%Y%m%d"))


# --------------------------------------------------------------------------- #
# Generators                                                                   #
# --------------------------------------------------------------------------- #
def gen_users(n: int, now: datetime, days: int) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "id": sample_user_id(i),
            "display_name": f"Sample User {i}",
            "native_language": rng.choice(NATIVE),
            "created_at": rand_dt(now, days + 30).isoformat(),  # joined a bit earlier
        })
    return rows


def _exercise_rows(lesson_id: str, language: str, mode: str, verb: str | None) -> list[dict]:
    rows = []
    for idx in range(rng.randint(4, 8)):
        etype = rng.choice(EXERCISE_TYPES)
        target = verb or rng.choice(VERBS[language])
        if etype == "translation":
            q = f"Translate: 'I {target} every day.'"
            a = f"{target} — translated form"
        elif etype == "conjugation":
            q = f"Conjugate '{target}' (1st person singular)."
            a = f"{target} (yo/je/I form)"
        elif etype == "fill_blank":
            q = f"Complete the sentence with '{target}': ___ ."
            a = f"{target} (correct form)"
        else:
            q = f"Build a sentence using '{target}'."
            a = f"A correct sentence with {target}."
        rows.append({
            "id": str(uuid.uuid4()),
            "lesson_id": lesson_id,
            "order_index": idx,
            "exercise_type": etype,
            "question": q,
            "correct_answer": a,
            "hint": rng.choice(["Think about the tense.", "Mind the ending.", None]),
        })
    return rows


def gen_lessons_and_exercises(n: int, user_ids: list[str], now: datetime, days: int):
    lessons, exercises, lesson_index = [], [], {}
    for _ in range(n):
        lid = str(uuid.uuid4())
        language = rng.choice(LANGUAGES)
        mode = rng.choices(["scenario", "verb"], weights=[65, 35])[0]
        verb = rng.choice(VERBS[language]) if mode == "verb" else None
        scenario = None if mode == "verb" else rng.choice(SCENARIOS)
        difficulty = rng.choice(LEVELS)
        grammar = rng.choice(GRAMMAR_FOCUS)
        created = rand_dt(now, days)
        lessons.append({
            "id": lid,
            "user_id": rng.choice(user_ids),
            "target_language": language,
            "scenario": scenario or (f"Verb practice: {verb}" if verb else "Practice"),
            "mode": mode,
            "verb": verb,
            "grammar_focus": grammar,
            "difficulty": difficulty,
            "worksheet_json": "{}",
            "version": 1,
            "created_at": created.isoformat(),
        })
        ex_rows = _exercise_rows(lid, language, mode, verb)
        exercises.extend(ex_rows)
        lesson_index[lid] = {"row": lessons[-1], "exercises": ex_rows, "created": created}
    return lessons, exercises, lesson_index


def _graded_response(ex: dict) -> dict:
    first = weighted_score()
    first_ok = first >= 0.75
    if first_ok:
        final, attempts = first, 1
    else:
        final = min(1.0, first + rng.choice([0.25, 0.5, 0.75]))
        attempts = rng.randint(2, 3)
    return {
        "exercise_id": ex["id"],
        "order_index": ex["order_index"],
        "exercise_type": ex["exercise_type"],
        "question": ex["question"],
        "correct_answer": ex["correct_answer"],
        "user_answer": ex["correct_answer"] if final >= 0.75 else "partial attempt",
        "first_score": first,
        "first_is_correct": first_ok,
        "final_score": final,
        "final_is_correct": final >= 0.75,
        "attempts": attempts,
        "feedback": rng.choice(FEEDBACK),
    }


def gen_submissions(n: int, lesson_index: dict, now: datetime, days: int):
    headers, details = [], []
    lesson_ids = list(lesson_index.keys())
    for _ in range(n):
        lid = rng.choice(lesson_ids)
        info = lesson_index[lid]
        lesson = info["row"]
        exs = info["exercises"]
        sub_id = str(uuid.uuid4())
        # submitted shortly after the lesson was created, still within the window
        base = info["created"]
        submitted = base + timedelta(minutes=rng.randint(5, 4320))
        if submitted > now:
            submitted = now - timedelta(minutes=rng.randint(5, 600))
        sub_date = submitted.date()

        responses = [_graded_response(ex) for ex in exs]
        # a few exercises may be left unanswered
        for r in rng.sample(responses, k=rng.randint(0, max(0, len(responses) // 4))):
            r["user_answer"] = ""
        answered = [r for r in responses if r["user_answer"].strip()]
        fs = [r["first_score"] for r in answered]
        fns = [r["final_score"] for r in answered]

        headers.append({
            "submission_id": sub_id,
            "lesson_id": lid,
            "user_id": lesson["user_id"],
            "target_language": lesson["target_language"],
            "mode": lesson["mode"],
            "verb": lesson["verb"],
            "scenario": lesson["scenario"],
            "difficulty": lesson["difficulty"],
            "grammar_focus": lesson["grammar_focus"],
            "total_exercises": len(responses),
            "answered_count": len(answered),
            "first_correct_count": sum(1 for r in answered if r["first_is_correct"]),
            "final_correct_count": sum(1 for r in answered if r["final_is_correct"]),
            "first_score_avg": round(sum(fs) / len(fs), 4) if fs else 0.0,
            "final_score_avg": round(sum(fns) / len(fns), 4) if fns else 0.0,
            "submitted_at": submitted.isoformat(),
            "date_key": date_key(sub_date),
        })
        for r in responses:
            details.append({
                "response_id": str(uuid.uuid4()),
                "submission_id": sub_id,
                "lesson_id": lid,
                "user_id": lesson["user_id"],
                "exercise_id": r["exercise_id"],
                "order_index": r["order_index"],
                "exercise_type": r["exercise_type"],
                "question": r["question"],
                "correct_answer": r["correct_answer"],
                "user_answer": r["user_answer"],
                "first_score": r["first_score"],
                "first_is_correct": r["first_is_correct"],
                "final_score": r["final_score"],
                "final_is_correct": r["final_is_correct"],
                "attempts": r["attempts"],
                "feedback": r["feedback"],
                "target_language": lesson["target_language"],
                "difficulty": lesson["difficulty"],
                "mode": lesson["mode"],
                "submitted_at": submitted.isoformat(),
                "date_key": date_key(sub_date),
            })
    return headers, details


def gen_exercise_scores(n: int, exercises: list[dict], lesson_index: dict,
                        now: datetime, days: int) -> list[dict]:
    rows = []
    # map exercise_id -> owning lesson's user for plausible attribution
    ex_to_user = {}
    for info in lesson_index.values():
        uid = info["row"]["user_id"]
        for ex in info["exercises"]:
            ex_to_user[ex["id"]] = uid
    for _ in range(n):
        ex = rng.choice(exercises)
        score = weighted_score()
        rows.append({
            "id": str(uuid.uuid4()),
            "exercise_id": ex["id"],
            "user_id": ex_to_user.get(ex["id"]),
            "user_answer": ex["correct_answer"] if score >= 0.75 else "attempt",
            "is_correct": score >= 0.75,
            "score": score,
            "feedback": rng.choice(FEEDBACK),
            "created_at": rand_dt(now, days).isoformat(),
        })
    return rows


def gen_conversations(n: int, user_ids: list[str], now: datetime, days: int):
    convos, turns = [], []
    for _ in range(n):
        cid = str(uuid.uuid4())
        language = rng.choice(LANGUAGES)
        uid = rng.choice(user_ids)
        created = rand_dt(now, days)
        n_turns = rng.randint(4, 12)
        ended = created + timedelta(minutes=rng.randint(3, 30))
        ctx = rng.choices(
            [None, rng.choice(SCENARIOS),
             "Current-events chat grounded in today's news."],
            weights=[40, 45, 15],
        )[0]
        convos.append({
            "id": cid,
            "user_id": uid,
            "target_language": language,
            "scenario_context": ctx,
            "created_at": created.isoformat(),
            "ended_at": ended.isoformat(),
        })
        for ti in range(n_turns):
            role = "user" if ti % 2 == 0 else "assistant"
            text = rng.choice(TURN_TEXT[language])
            turns.append({
                "id": str(uuid.uuid4()),
                "conversation_id": cid,
                "role": role,
                "text": text,
                "corrected_text": (text + " (corrected)") if role == "user" and rng.random() < 0.3 else None,
                "turn_index": ti,
                "created_at": (created + timedelta(seconds=ti * rng.randint(20, 90))).isoformat(),
            })
    return convos, turns


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #
def validate(table: str, rows: list[dict]) -> None:
    """Coerce + build an Arrow table against the authoritative schema (raises on mismatch)."""
    schema = store._SCHEMAS[table]
    coerced = [store._coerce(r, schema) for r in rows]
    pa.Table.from_pylist(coerced, schema=schema)


async def main() -> None:
    ap = argparse.ArgumentParser(description="Seed sample data into the Lakehouse (dbo).")
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--lessons", type=int, default=1500)
    ap.add_argument("--submissions", type=int, default=2000)
    ap.add_argument("--scores", type=int, default=2500)
    ap.add_argument("--conversations", type=int, default=1200)
    ap.add_argument("--days", type=int, default=30, help="spread timestamps over the past N days")
    ap.add_argument("--dry-run", action="store_true", help="build + validate, do not write")
    ap.add_argument("--force", action="store_true", help="proceed even if sample users already exist")
    args = ap.parse_args()

    s = store.get_lakehouse()._settings
    print(f"backend={s.storage_backend}  schema={s.onelake_schema!r}")

    now = datetime.now(timezone.utc)

    print("Generating rows…")
    users = gen_users(args.users, now, args.days)
    user_ids = [u["id"] for u in users]
    lessons, exercises, lesson_index = gen_lessons_and_exercises(args.lessons, user_ids, now, args.days)
    sub_headers, sub_details = gen_submissions(args.submissions, lesson_index, now, args.days)
    ex_scores = gen_exercise_scores(args.scores, exercises, lesson_index, now, args.days)
    convos, turns = gen_conversations(args.conversations, user_ids, now, args.days)

    batches = {
        store.USERS: users,
        store.LESSONS: lessons,
        store.EXERCISES: exercises,
        store.WORKSHEET_SUBMISSIONS: sub_headers,
        store.WORKSHEET_RESPONSES: sub_details,
        store.EXERCISE_SCORES: ex_scores,
        store.CONVERSATIONS: convos,
        store.CONVERSATION_TURNS: turns,
    }

    print("\nPlanned row counts:")
    for t, rows in batches.items():
        print(f"  {t:<22} {len(rows):>7}")

    print("\nValidating against authoritative schemas…")
    for t, rows in batches.items():
        validate(t, rows)
    print("  all batches schema-valid ✓")

    if args.dry_run:
        print("\n--dry-run: no data written.")
        return

    lake = get_lakehouse()

    # Guard against accidental double-seeding.
    if not args.force:
        existing_users = await lake.read_all(store.USERS, store._SCHEMAS[store.USERS])
        if any((u.get("id") or "").startswith(SAMPLE_PREFIX) for u in existing_users):
            print("\nSample users already present — re-run with --force to add more. Aborting.")
            return

    # Ensure the calendar dimension covers the generated window.
    earliest = (now - timedelta(days=args.days + 30)).date()
    await store.ensure_date_dim(through=now.date())
    print(f"\ndate_dim ensured (covers ≥ {earliest} … {now.date()}).")

    print("Writing batches (one Delta commit per table)…")
    for t, rows in batches.items():
        coerced = [store._coerce(r, store._SCHEMAS[t]) for r in rows]
        await lake.append(t, coerced, store._SCHEMAS[t])
        print(f"  wrote {len(rows):>7} → dbo.{t}")

    print("\nDone. Sample users use GUID prefix "
          f"'{SAMPLE_PREFIX[:8]}…' (delete where user_id LIKE '{SAMPLE_PREFIX[:8]}%' to undo).")


if __name__ == "__main__":
    asyncio.run(main())
