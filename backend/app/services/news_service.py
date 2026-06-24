"""
News retrieval service.

Reads enriched current-events news from the RTI store and shapes it for two
consumers:

* the **picker API** — a list of today's topics in the target language, graded
  near the learner's CEFR level;
* the **conversation grounding** — a briefing string injected into a tutor
  session so the AI discusses a real, current news item (RAG over the hot path).

Personalization (the "closed loop") is best-effort: when an embedding deployment
is configured we build a short interest/weakness query from the learner's recent
worksheet submissions (weak grammar focuses / verbs) and rank news by semantic
similarity, so today's article tends to exercise the skills they struggle with.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.repository import eventhouse, store
from app.services.llm_service import embed_text

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"en": "English", "fr": "French", "es": "Spanish"}


def _shape_topic(rec: dict) -> dict:
    """Public, picker-friendly view of an enriched article."""
    return {
        "news_id": rec.get("news_id"),
        "title": rec.get("title_translated") or rec.get("title_original"),
        "summary": rec.get("summary"),
        "english_gloss": rec.get("english_gloss"),
        "cefr_level": rec.get("cefr_level"),
        "topic_tags": rec.get("topic_tags") or [],
        "verbs": rec.get("verbs") or [],
        "vocabulary": rec.get("vocabulary") or [],
        "conversation_starters": rec.get("conversation_starters") or [],
        "domain": rec.get("domain"),
        "url": rec.get("url"),
        "language": rec.get("language"),
        "seen_at": rec.get("seen_at"),
    }


async def _learner_interest_text(user_id: str | None) -> str:
    """Best-effort interest/weakness query from recent weak submissions."""
    if not user_id:
        return ""
    try:
        subs, _ = await store.list_submissions(user_id, page=1, page_size=10)
    except Exception as exc:  # noqa: BLE001 - personalization is optional
        logger.debug("Could not read submissions for personalization: %s", exc)
        return ""

    terms: list[str] = []
    for sub in subs:
        # Prefer the areas the learner scored lowest on.
        weak = (sub.get("final_score_avg") is not None) and (sub.get("final_score_avg") < 0.8)
        if weak or not terms:
            for key in ("grammar_focus", "verb", "scenario"):
                val = (sub.get(key) or "").strip()
                if val and val.lower() not in {"none", "null"}:
                    terms.append(val)
    # De-dup, keep order, cap length.
    seen: set[str] = set()
    unique = [t for t in terms if not (t.lower() in seen or seen.add(t.lower()))]
    return ", ".join(unique[:6])


async def get_topics(
    language: str,
    *,
    level: str | None = None,
    limit: int = 12,
    user_id: str | None = None,
    personalized: bool = False,
) -> list[dict]:
    """Return today's current-events topics for ``language``.

    When ``personalized`` and an embedding deployment is configured, results are
    re-ranked toward the learner's weak skills; otherwise they are most-recent
    first, kept within ~one CEFR level of ``level``.
    """
    s = get_settings()
    level = level or s.news_default_level

    if personalized:
        interest = await _learner_interest_text(user_id)
        query_vec = await embed_text(interest) if interest else None
        if query_vec:
            ranked = await eventhouse.search_by_vector(
                language,
                query_vec,
                level=level,
                limit=limit,
                max_age_hours=s.news_max_age_hours,
            )
            return [_shape_topic(r) for r in ranked]

    rows = await eventhouse.get_recent(
        language, level=level, limit=limit, max_age_hours=s.news_max_age_hours
    )
    return [_shape_topic(r) for r in rows]


async def get_article(news_id: str) -> dict | None:
    rec = await eventhouse.get_by_id(news_id)
    return _shape_topic(rec) if rec else None


async def build_conversation_context(news_id: str, *, fallback: str | None = None) -> str | None:
    """Compose a tutor briefing string grounding a session in one news item."""
    rec = await eventhouse.get_by_id(news_id)
    if not rec:
        return fallback

    lang_name = LANGUAGE_NAMES.get(rec.get("language", ""), rec.get("language", ""))
    title = rec.get("title_translated") or rec.get("title_original") or ""
    summary = rec.get("summary") or title
    vocab = rec.get("vocabulary") or []
    starters = rec.get("conversation_starters") or []

    lines = [
        f"Discuss this current-events news with the learner in {lang_name}, like two people "
        f"reacting to today's headlines.",
        f"NEWS HEADLINE: {title}",
        f"NEWS SUMMARY: {summary}",
        "Only rely on the facts in this summary — do not invent specific numbers, names or "
        "quotes. Invite the learner to react, give opinions and ask their own questions.",
    ]
    if vocab:
        pairs = ", ".join(f"{v.get('word')} ({v.get('translation')})" for v in vocab[:6] if v.get("word"))
        if pairs:
            lines.append(f"You may naturally introduce useful vocabulary: {pairs}.")
    if starters:
        lines.append("Good opening questions: " + " ".join(f"({i+1}) {q}" for i, q in enumerate(starters[:3])))
    if fallback:
        lines.append(f"Additional context from the learner: {fallback}")
    return "\n".join(lines)
