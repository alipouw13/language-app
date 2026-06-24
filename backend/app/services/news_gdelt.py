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
from datetime import datetime, timedelta, timezone

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
    """Return a small fixed set of articles for offline dev/testing.

    Note: these have stable URLs, so re-ingesting them is a no-op once stored
    (deduped by URL hash). Use :func:`synthetic_articles` to generate fresh,
    unique articles on demand.
    """
    now = datetime.now(timezone.utc).isoformat()
    return [{**a, "seen_at": now} for a in _SAMPLE.get(language, [])]


# --------------------------------------------------------------------------- #
# Synthetic source — fresh, varied articles with unique URLs every run.        #
# Lets you populate the news store on demand without GDELT (no rate limits).   #
# --------------------------------------------------------------------------- #
import random  # noqa: E402  (kept local to the synthetic source)

_SYN_META = {
    "es": ("Spanish", "Spain", "es"),
    "fr": ("French", "France", "fr"),
    "en": ("English", "United States", "en"),
}

# (headline template, slug) pairs per language across varied topics. ``{x}`` is
# filled from the matching subject pool so each run yields different combinations.
_SYN_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "es": [
        ("La ciudad de {x} inaugura una nueva línea de tranvía eléctrico", "tranvia"),
        ("Científicos de {x} desarrollan una batería que dura el doble", "bateria"),
        ("El festival de cine de {x} bate récord de asistencia este año", "cine"),
        ("Agricultores de {x} apuestan por el cultivo sostenible del olivo", "olivo"),
        ("La selección de {x} se clasifica para la final del torneo", "futbol"),
        ("Un nuevo museo de arte digital abre sus puertas en {x}", "museo"),
        ("{x} reduce un 20% el uso de plástico en sus mercados", "plastico"),
        ("Investigadores descubren restos romanos en el centro de {x}", "romanos"),
        ("La cocina tradicional de {x} gana un premio internacional", "cocina"),
        ("El turismo rural crece con fuerza en la región de {x}", "turismo"),
    ],
    "fr": [
        ("La ville de {x} lance un réseau de vélos électriques partagés", "velos"),
        ("Des chercheurs de {x} mettent au point un panneau solaire plus léger", "solaire"),
        ("Le festival de musique de {x} attire un public record cette année", "festival"),
        ("Les boulangers de {x} défendent la baguette artisanale", "baguette"),
        ("L'équipe de {x} remporte le championnat après dix ans", "championnat"),
        ("Un nouveau parc naturel ouvre près de {x}", "parc"),
        ("{x} inaugure une ligne de train à grande vitesse vers le sud", "tgv"),
        ("Des archéologues révèlent une mosaïque gauloise à {x}", "mosaique"),
        ("La gastronomie de {x} séduit les critiques internationaux", "gastronomie"),
        ("Le tourisme à vélo se développe dans la région de {x}", "tourisme"),
    ],
    "en": [
        ("The city of {x} opens a new electric ferry route", "ferry"),
        ("Researchers in {x} build a cheaper way to recycle batteries", "battery"),
        ("The {x} film festival draws record crowds this year", "film"),
        ("Local farmers near {x} switch to regenerative agriculture", "farming"),
        ("The {x} team wins the league after a decade", "league"),
        ("A new science museum opens its doors in {x}", "museum"),
        ("{x} cuts single-use plastic in its markets by a fifth", "plastic"),
        ("Archaeologists uncover a medieval street under {x}", "dig"),
        ("Street food from {x} wins an international award", "food"),
        ("Cycling tourism is booming in the {x} region", "cycling"),
    ],
}

_SYN_SUBJECTS: dict[str, list[str]] = {
    "es": ["Valencia", "Sevilla", "Bilbao", "Granada", "Málaga", "Zaragoza",
           "Salamanca", "Córdoba", "Toledo", "Santander", "Murcia", "Gijón"],
    "fr": ["Lyon", "Marseille", "Bordeaux", "Lille", "Nantes", "Strasbourg",
           "Toulouse", "Rennes", "Nice", "Dijon", "Grenoble", "Reims"],
    "en": ["Portland", "Austin", "Denver", "Seattle", "Bristol", "Leeds",
           "Calgary", "Dublin", "Boulder", "Madison", "Tucson", "Raleigh"],
}

_SYN_DOMAINS = ["noticiaslocales.example", "diarioregional.example", "lejournal.example",
                "citytimes.example", "actualites.example", "newsdaily.example"]


def synthetic_articles(language: str, count: int = 8) -> list[dict]:
    """Generate ``count`` fresh, unique synthetic articles for a language.

    Headlines are random template/subject combinations and every URL carries a
    timestamp + random token, so the articles are always *new* (pass dedup) and
    flow through the full enrichment + ingestion pipeline — ideal for demos and
    populating the store without hitting GDELT.
    """
    lang = language if language in _SYN_TEMPLATES else "en"
    lang_name, country, code = _SYN_META[lang]
    templates = _SYN_TEMPLATES[lang]
    subjects = _SYN_SUBJECTS[lang]
    now_dt = datetime.now(timezone.utc)
    stamp = now_dt.strftime("%Y%m%d%H%M%S")

    out: list[dict] = []
    chosen = random.sample(templates, k=min(count, len(templates)))
    # If more than the template count is requested, allow repeats with new subjects.
    while len(chosen) < count:
        chosen.append(random.choice(templates))

    for i, (template, slug) in enumerate(chosen):
        subject = random.choice(subjects)
        token = f"{random.randint(100000, 999999):06d}"
        domain = random.choice(_SYN_DOMAINS)
        title = template.format(x=subject)
        # Unique URL every run → always counts as a "new" article.
        url = f"https://{domain}/{code}/{slug}-{subject.lower()}-{stamp}-{token}"
        # Spread timestamps over the last few hours for realistic recency.
        seen = (now_dt - timedelta(minutes=15 * i)).isoformat()
        out.append({
            "url": url,
            "title": title,
            "domain": domain,
            "language": lang_name,
            "source_country": country,
            "social_image": "",
            "seen_at": seen,
        })
    return out
