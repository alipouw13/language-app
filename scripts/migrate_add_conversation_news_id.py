"""Migration: add `news_id` to the conversations Delta table + backfill.

The `conversations` table predates the `news_id` column. delta-rs append refuses
to write a wider schema, so this one-time migration rewrites the table with the
new schema (overwrite evolves it) and:

  * sets news_id = None for every existing row, then
  * backfills a real news_id (from the configured RTI store) onto conversations
    whose scenario_context indicates a current-events / news-grounded chat, so the
    Gold news <-> conversation join is demonstrable.

Idempotent: if the table already has the news_id column it only backfills rows
that are still missing one.

Run from backend/ so backend/.env loads:

    cd backend
    python ../scripts/migrate_add_conversation_news_id.py --dry-run
    python ../scripts/migrate_add_conversation_news_id.py
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, "backend")
sys.path.insert(0, ".")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from app.config import get_settings  # noqa: E402
from app.repository import eventhouse, store  # noqa: E402
from app.repository.lakehouse import get_lakehouse  # noqa: E402

NEWS_MARKERS = ("news", "current-events", "current events", "headline", "noticias", "actualité")
rng = random.Random(7)


def _is_news_grounded(conv: dict) -> bool:
    ctx = (conv.get("scenario_context") or "").lower()
    return any(m in ctx for m in NEWS_MARKERS)


async def _available_news_ids() -> list[str]:
    """Collect news_ids from the configured RTI store across languages (best-effort)."""
    ids: list[str] = []
    s = get_settings()
    for lang in (s.news_languages or ["es", "fr", "en"]):
        try:
            rows = await eventhouse.get_recent(lang, limit=200, max_age_hours=24 * 365)
            ids.extend(r["news_id"] for r in rows if r.get("news_id"))
        except Exception as exc:  # noqa: BLE001
            print(f"  (warn) could not read RTI news for {lang}: {str(exc)[:100]}")
    return list(dict.fromkeys(ids))  # dedupe, preserve order


async def main() -> None:
    ap = argparse.ArgumentParser(description="Add + backfill conversations.news_id")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lake = get_lakehouse()
    schema = store._SCHEMAS[store.CONVERSATIONS]
    s = get_settings()
    print(f"backend={s.storage_backend}  schema={s.onelake_schema!r}  rti={s.rti_backend}")

    rows = await lake.read_all(store.CONVERSATIONS, schema)
    print(f"conversations read: {len(rows)}")
    if not rows:
        print("No conversations to migrate.")
        return

    has_col = any("news_id" in r for r in rows)
    print(f"news_id column already present: {has_col}")

    news_ids = await _available_news_ids()
    print(f"available RTI news_ids for backfill: {len(news_ids)}")

    coerced = [store._coerce(r, schema) for r in rows]  # adds news_id=None where missing
    candidates = [c for c, original in zip(coerced, rows) if _is_news_grounded(original)]
    backfilled = 0
    if news_ids:
        for c in candidates:
            if not c.get("news_id"):
                c["news_id"] = rng.choice(news_ids)
                backfilled += 1
    print(f"news-grounded conversations: {len(candidates)}  -> backfilled news_id: {backfilled}")

    if args.dry_run:
        print("--dry-run: no write.")
        return

    # Overwrite rewrites the table with the new (wider) schema and the backfilled rows.
    await lake.overwrite(store.CONVERSATIONS, coerced, schema)
    print(f"Overwrote dbo.conversations with {len(coerced)} rows (schema now includes news_id).")


if __name__ == "__main__":
    asyncio.run(main())
