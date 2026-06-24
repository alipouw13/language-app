"""
GDELT news source client.

Pulls recent, real-world news articles from the free GDELT DOC 2.0 API
(https://api.gdeltproject.org/api/v2/doc/doc). GDELT is multilingual and
near real-time, which makes it a good source for *current-events* conversation
practice. We only take lightweight article metadata here (title, url, domain,
language, timestamp); semantic enrichment (translation, grading, embeddings)
happens later in ``news_ingestion`` using the Foundry models.

GDELT rate-limits anonymous callers (roughly one request every 5s), so the
ingestion layer paces per-language calls. For offline development a small
``sample_articles`` fixture lets the whole loop run without network access.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT serves a plain, honest User-Agent fine but aggressively rate-limits
# browser-spoofing UAs (Mozilla/Chrome strings). Keep it simple and truthful.
_USER_AGENT = "language-app/1.0 (+https://github.com/alipouw13/language-app)"

# GDELT's free DOC API asks for no more than one request every 5 seconds and
# penalizes bursts with extended 429 cooldowns. Enforce a process-wide minimum
# spacing between *any* GDELT calls so concurrent/looping callers never burst.
_MIN_INTERVAL_SECONDS = 6.0
_RATE_LOCK = asyncio.Lock()
_last_call_at = 0.0

# Retry policy for transient 429 / network errors.
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 12.0

# App language code → GDELT ``sourcelang`` token.
_GDELT_LANG = {"es": "spanish", "fr": "french", "en": "english"}

# Current-events queries per language. Kept lightweight (GDELT treats heavy
# boolean queries with high maxrecords as "larger queries" and throttles them
# harder). A couple of OR'd everyday terms still yields a varied news mix.
_DEFAULT_QUERY = {
    "es": "(noticias OR actualidad)",
    "fr": "(actualité OR information)",
    "en": "(news OR headlines)",
}


class NewsSourceError(RuntimeError):
    """Raised when the news source returns a non-JSON / error response."""


def _parse_seendate(value: str) -> str:
    """Convert GDELT's ``YYYYMMDDTHHMMSSZ`` stamp to ISO-8601 UTC."""
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def _normalize(article: dict) -> dict | None:
    """Normalize a raw GDELT article into our internal shape."""
    url = (article.get("url") or "").strip()
    title = (article.get("title") or "").strip()
    if not url or not title:
        return None
    return {
        "url": url,
        "title": title,
        "domain": (article.get("domain") or "").strip(),
        "language": (article.get("language") or "").strip(),
        "source_country": (article.get("sourcecountry") or "").strip(),
        "social_image": (article.get("socialimage") or "").strip(),
        "seen_at": _parse_seendate(article.get("seendate", "")),
    }


async def _throttle() -> None:
    """Block until at least ``_MIN_INTERVAL_SECONDS`` since the last GDELT call."""
    global _last_call_at
    async with _RATE_LOCK:
        wait = _MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call_at = time.monotonic()


async def _get_with_retry(params: dict, *, timeout: float) -> httpx.Response:
    """GET the GDELT endpoint with global throttling + retry/backoff on 429."""
    headers = {"User-Agent": _USER_AGENT, "Accept": "*/*"}
    last_status = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        await _throttle()
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                resp = await client.get(GDELT_DOC_URL, params=params)
            resp.raise_for_status()
            body = resp.text or ""
            # GDELT returns 200 with a plain-text limit notice in some cases.
            if not body.lstrip().startswith("{"):
                raise httpx.HTTPStatusError(
                    "rate-limit notice", request=resp.request, response=resp
                )
            return resp
        except httpx.HTTPStatusError as exc:
            last_status = exc.response.status_code if exc.response is not None else None
            transient = last_status in (429, 500, 502, 503) or last_status is None
            if attempt < _MAX_ATTEMPTS and transient:
                delay = _BACKOFF_SECONDS * attempt
                logger.info(
                    "GDELT %s — retry %d/%d in %.0fs",
                    last_status, attempt, _MAX_ATTEMPTS, delay,
                )
                await asyncio.sleep(delay)
                continue
            raise NewsSourceError(f"GDELT HTTP {last_status}") from exc
        except httpx.HTTPError as exc:  # timeouts, connection errors
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(_BACKOFF_SECONDS * attempt)
                continue
            raise NewsSourceError(f"GDELT request failed: {exc}") from exc
    raise NewsSourceError(f"GDELT unavailable after {_MAX_ATTEMPTS} attempts")


async def fetch_articles(
    language: str,
    *,
    timespan: str = "1d",
    max_records: int = 40,
    query: str | None = None,
    timeout: float = 20.0,
) -> list[dict]:
    """Fetch recent articles in ``language`` from GDELT.

    Returns a list of normalized article dicts (most recent first). Requests are
    globally throttled (≥6s apart) and retried with backoff on 429, since the
    free GDELT API penalizes bursts. Raises :class:`NewsSourceError` when GDELT
    stays unavailable so callers can skip the language gracefully.
    """
    sourcelang = _GDELT_LANG.get(language)
    if not sourcelang:
        raise ValueError(f"Unsupported news language: {language!r}")

    base_query = (query or _DEFAULT_QUERY.get(language) or "").strip()
    full_query = f"{base_query} sourcelang:{sourcelang}".strip()
    params = {
        "query": full_query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(max_records),
        "timespan": timespan,
        "sort": "DateDesc",
    }

    resp = await _get_with_retry(params, timeout=timeout)

    try:
        payload = resp.json()
    except ValueError as exc:  # pragma: no cover - defensive
        raise NewsSourceError(f"GDELT returned invalid JSON: {resp.text[:200]}") from exc

    articles = payload.get("articles") or []
    out: list[dict] = []
    for raw in articles:
        norm = _normalize(raw)
        if norm:
            out.append(norm)
    logger.info("GDELT: fetched %d %s articles", len(out), language)
    return out


# --------------------------------------------------------------------------- #
# Offline sample — lets the ingestion + conversation loop run with no network. #
# --------------------------------------------------------------------------- #
_SAMPLE: dict[str, list[dict]] = {
    "es": [
        {
            "url": "https://example.com/es/energia-solar",
            "title": "España bate su récord de generación de energía solar este verano",
            "domain": "example.com",
            "language": "Spanish",
            "source_country": "Spain",
            "social_image": "",
        },
        {
            "url": "https://example.com/es/liga-femenina",
            "title": "La liga femenina de fútbol anuncia una ampliación a dieciséis equipos",
            "domain": "example.com",
            "language": "Spanish",
            "source_country": "Spain",
            "social_image": "",
        },
    ],
    "fr": [
        {
            "url": "https://example.com/fr/train-nuit",
            "title": "La France relance plusieurs lignes de trains de nuit vers le sud",
            "domain": "example.com",
            "language": "French",
            "source_country": "France",
            "social_image": "",
        },
    ],
    "en": [
        {
            "url": "https://example.com/en/city-bikes",
            "title": "City doubles its network of protected bike lanes in one year",
            "domain": "example.com",
            "language": "English",
            "source_country": "United States",
            "social_image": "",
        },
    ],
}


def sample_articles(language: str) -> list[dict]:
    """Return a small fixed set of articles for offline dev/testing."""
    now = datetime.now(timezone.utc).isoformat()
    return [{**a, "seen_at": now} for a in _SAMPLE.get(language, [])]
