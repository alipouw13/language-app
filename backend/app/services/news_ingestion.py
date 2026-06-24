"""
News ingestion + enrichment.

Turns raw GDELT headlines into *learner-ready* current-events records and writes
them to the RTI store (:mod:`app.repository.eventhouse`). Enrichment uses the
chat model to produce a level-graded summary, discussion prompts, key vocabulary
and grammar tags, and (optionally) an embedding for semantic retrieval.

Grounding rule: the model is told to stay close to the headline and *not invent
specific facts, numbers or quotes* — the headline is the only ground truth we
have, so summaries are framed as discussion seeds rather than reportage.

Enrichment degrades gracefully: if the chat model is unavailable, a minimal
record is produced from the headline so the loop still runs (useful with the
offline ``sample`` source).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.repository import eventhouse
from app.services import news_gdelt
from app.services.llm_service import chat_completion_json, embed_text

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"en": "English", "fr": "French", "es": "Spanish"}
_VALID_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
_MAX_CONCURRENCY = 4


def _enrichment_messages(article: dict, language: str, level: str) -> list[dict[str, str]]:
    lang_name = LANGUAGE_NAMES.get(language, language)
    headline = article["title"]
    domain = article.get("domain", "")
    system = (
        f"You prepare authentic, current-events news for {lang_name} language learners. "
        f"You are given a real news HEADLINE. Produce study material in {lang_name} aimed "
        f"at CEFR level {level}. Stay strictly faithful to the headline: do NOT invent "
        f"specific facts, figures, names or quotes that are not in it — write a short, "
        f"general, discussion-oriented summary. Respond with a single JSON object only."
    )
    user = (
        f"HEADLINE ({lang_name}): {headline}\n"
        f"SOURCE: {domain}\n\n"
        "Return JSON with exactly these keys:\n"
        f'  "title_translated": the headline cleaned up, in {lang_name};\n'
        f'  "summary": 2-3 sentences in {lang_name} at level {level}, faithful to the headline;\n'
        '  "english_gloss": one short English sentence describing the topic (for a picker);\n'
        '  "cefr_level": the actual level of your summary, one of A1,A2,B1,B2,C1,C2;\n'
        '  "topic_tags": 2-4 short topic tags (lowercase, in English);\n'
        f'  "verbs": 3-6 key verbs from the summary as infinitives in {lang_name};\n'
        '  "tenses": grammatical tenses present (English names, e.g. "present", "preterite");\n'
        f'  "conversation_starters": 3 open questions in {lang_name} to discuss this topic;\n'
        f'  "vocabulary": 4-6 objects {{"word": {lang_name} word, "translation": English}}.'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _as_str_list(value, limit: int = 8) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()][:limit]
    return []


def _as_vocab(value, limit: int = 8) -> list[dict]:
    out: list[dict] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("word"):
                out.append(
                    {
                        "word": str(item.get("word", "")).strip(),
                        "translation": str(item.get("translation", "")).strip(),
                    }
                )
    return out[:limit]


def _minimal_record(article: dict, language: str, level: str) -> dict:
    """Fallback enrichment when the chat model is unavailable."""
    now = datetime.now(timezone.utc).isoformat()
    title = article["title"]
    return {
        "news_id": eventhouse.news_id_for(article["url"]),
        "url": article["url"],
        "domain": article.get("domain", ""),
        "language": language,
        "source_country": article.get("source_country", ""),
        "title_original": title,
        "title_translated": title,
        "summary": title,
        "english_gloss": "",
        "cefr_level": level if level in _VALID_LEVELS else "B1",
        "topic_tags": [],
        "verbs": [],
        "tenses": [],
        "conversation_starters": [],
        "vocabulary": [],
        "embedding": None,
        "seen_at": article.get("seen_at", now),
        "ingested_at": now,
    }


async def enrich_article(article: dict, language: str, level: str) -> dict:
    """Build an enriched RTI record for one article."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        data = await chat_completion_json(
            _enrichment_messages(article, language, level),
            temperature=0.4,
            max_tokens=1200,
        )
    except Exception as exc:  # noqa: BLE001 - never let one article break the batch
        logger.warning("Enrichment failed for %s (%s); using minimal record", article["url"], exc)
        return _minimal_record(article, language, level)

    cefr = str(data.get("cefr_level", "")).upper().strip()
    summary = str(data.get("summary", "")).strip() or article["title"]

    record = {
        "news_id": eventhouse.news_id_for(article["url"]),
        "url": article["url"],
        "domain": article.get("domain", ""),
        "language": language,
        "source_country": article.get("source_country", ""),
        "title_original": article["title"],
        "title_translated": str(data.get("title_translated", "")).strip() or article["title"],
        "summary": summary,
        "english_gloss": str(data.get("english_gloss", "")).strip(),
        "cefr_level": cefr if cefr in _VALID_LEVELS else (level if level in _VALID_LEVELS else "B1"),
        "topic_tags": _as_str_list(data.get("topic_tags")),
        "verbs": _as_str_list(data.get("verbs")),
        "tenses": _as_str_list(data.get("tenses")),
        "conversation_starters": _as_str_list(data.get("conversation_starters"), limit=4),
        "vocabulary": _as_vocab(data.get("vocabulary")),
        "embedding": None,
        "seen_at": article.get("seen_at", now),
        "ingested_at": now,
    }

    try:
        embed_input = f"{record['title_translated']}. {summary} {' '.join(record['topic_tags'])}"
        record["embedding"] = await embed_text(embed_input)
    except Exception as exc:  # noqa: BLE001 - embedding is optional
        logger.warning("Embedding failed for %s (%s)", article["url"], exc)

    return record


async def _gather_articles(language: str, *, source: str, max_records: int, timespan: str, query: str | None) -> list[dict]:
    if source == "sample":
        return news_gdelt.sample_articles(language)
    if source == "synthetic":
        return news_gdelt.synthetic_articles(language, count=max_records)
    try:
        return await news_gdelt.fetch_articles(
            language, timespan=timespan, max_records=max_records, query=query
        )
    except news_gdelt.NewsSourceError as exc:
        logger.warning("News source error for %s (%s); skipping language", language, exc)
        return []


async def ingest_language(
    language: str,
    *,
    level: str | None = None,
    source: str = "gdelt",
    max_records: int | None = None,
    timespan: str | None = None,
    query: str | None = None,
    count: int | None = None,
) -> dict:
    """Fetch, dedup, enrich and store news for one language."""
    s = get_settings()
    level = (level or s.news_default_level).upper()
    # For the synthetic source, --count controls how many to generate.
    if source == "synthetic":
        max_records = count or max_records or 8
    else:
        max_records = max_records or s.gdelt_max_records
    timespan = timespan or s.gdelt_timespan
    if query is None:
        query = getattr(s, f"gdelt_query_{language}", "") or None

    articles = await _gather_articles(
        language, source=source, max_records=max_records, timespan=timespan, query=query
    )
    fetched = len(articles)
    if not articles:
        return {"language": language, "fetched": 0, "new": 0, "ingested": 0}

    by_id = {eventhouse.news_id_for(a["url"]): a for a in articles}
    already = await eventhouse.existing_ids(list(by_id.keys()))
    new_articles = [a for nid, a in by_id.items() if nid not in already]

    semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

    async def _one(article: dict) -> dict:
        async with semaphore:
            return await enrich_article(article, language, level)

    records = await asyncio.gather(*(_one(a) for a in new_articles)) if new_articles else []
    ingested = await eventhouse.ingest_news(records)
    logger.info(
        "Ingest %s: fetched=%d new=%d ingested=%d", language, fetched, len(new_articles), ingested
    )
    return {"language": language, "fetched": fetched, "new": len(new_articles), "ingested": ingested}


async def run_poller(stop_event: asyncio.Event) -> None:
    """Ingest news on a timer until ``stop_event`` is set.

    Wired into the API lifespan when ``NEWS_POLL_ENABLED=true``. Each iteration
    is best-effort: failures are logged and the loop continues so a transient
    GDELT or enrichment error never takes the API down.
    """
    s = get_settings()
    interval = max(5, s.news_poll_interval_minutes) * 60
    logger.info(
        "News poller started (every %d min, languages=%s, rti_backend=%s)",
        s.news_poll_interval_minutes,
        s.news_languages,
        s.rti_backend,
    )
    while not stop_event.is_set():
        try:
            await eventhouse.ensure_ready()
            totals = await ingest_all(source="gdelt")
            logger.info(
                "News poller ingested: fetched=%d new=%d ingested=%d",
                totals["fetched"],
                totals["new"],
                totals["ingested"],
            )
        except Exception:  # noqa: BLE001 - keep polling despite transient errors
            logger.exception("News poller iteration failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
    logger.info("News poller stopped")


async def ingest_all(
    *,
    languages: list[str] | None = None,
    level: str | None = None,
    source: str = "gdelt",
    count: int | None = None,
) -> dict:
    """Ingest news for every configured language (paced for the GDELT rate limit)."""
    s = get_settings()
    languages = languages or s.news_languages
    results: list[dict] = []
    for idx, lang in enumerate(languages):
        if source == "gdelt" and idx > 0:
            await asyncio.sleep(6)  # respect GDELT's ~1 request / 5s limit
        results.append(await ingest_language(lang, level=level, source=source, count=count))
    totals = {
        "languages": languages,
        "fetched": sum(r["fetched"] for r in results),
        "new": sum(r["new"] for r in results),
        "ingested": sum(r["ingested"] for r in results),
        "per_language": results,
    }
    return totals
