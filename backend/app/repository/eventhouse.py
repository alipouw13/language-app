"""
Real-Time Intelligence store for enriched news.

This is the persistence boundary for the *hot path* — enriched, current-events
news records used to ground conversation practice. It mirrors the config-driven
design of :mod:`app.repository.lakehouse`: the same async API serves two backends

* ``rti_backend = "local"``       → a JSON file on disk (dev / tests, no Fabric)
* ``rti_backend = "eventhouse"``  → a Fabric **Eventhouse** (KQL database),
  ingested + queried with the Kusto SDK, authenticated with Microsoft Entra ID
  via ``DefaultAzureCredential``.

Records are *upserted by ``news_id``* (a hash of the article URL). Semantic
retrieval uses cosine similarity over the stored embedding — computed in Python
for the local backend and with ``series_cosine_similarity`` in KQL for
Eventhouse. When an article has no embedding, retrieval falls back to recency
and CEFR level.

The enriched-news schema (one record):
    news_id, url, domain, language, source_country,
    title_original, title_translated, summary, english_gloss,
    cefr_level, topic_tags[], verbs[], tenses[], conversation_starters[],
    vocabulary[{word, translation}], embedding[float]|None,
    seen_at (iso), ingested_at (iso)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# Column order / types shared by the Eventhouse DDL and ingestion mapping.
# (name, kql_type) — arrays and the embedding are stored as ``dynamic``.
NEWS_COLUMNS: list[tuple[str, str]] = [
    ("news_id", "string"),
    ("url", "string"),
    ("domain", "string"),
    ("language", "string"),
    ("source_country", "string"),
    ("title_original", "string"),
    ("title_translated", "string"),
    ("summary", "string"),
    ("english_gloss", "string"),
    ("cefr_level", "string"),
    ("topic_tags", "dynamic"),
    ("verbs", "dynamic"),
    ("tenses", "dynamic"),
    ("conversation_starters", "dynamic"),
    ("vocabulary", "dynamic"),
    ("embedding", "dynamic"),
    ("seen_at", "datetime"),
    ("ingested_at", "datetime"),
]

_LIST_FIELDS = {"topic_tags", "verbs", "tenses", "conversation_starters", "vocabulary"}

# CEFR ordering, used to keep articles within ~one level of the learner.
_CEFR_ORDER = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}


def news_id_for(url: str) -> str:
    """Stable id for an article (hash of its URL)."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Plain cosine similarity (no numpy dependency)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _within_level(record_level: str, target_level: str | None, *, tolerance: int = 1) -> bool:
    """True when the article's CEFR level is within ``tolerance`` of target."""
    if not target_level:
        return True
    r = _CEFR_ORDER.get((record_level or "").upper())
    t = _CEFR_ORDER.get(target_level.upper())
    if r is None or t is None:
        return True
    return abs(r - t) <= tolerance


# --------------------------------------------------------------------------- #
# Backend protocol                                                            #
# --------------------------------------------------------------------------- #
class _RtiBackend:
    async def ensure_ready(self) -> dict[str, Any]:
        raise NotImplementedError

    async def existing_ids(self, ids: list[str]) -> set[str]:
        raise NotImplementedError

    async def ingest(self, records: list[dict]) -> int:
        raise NotImplementedError

    async def get_by_id(self, news_id: str) -> dict | None:
        raise NotImplementedError

    async def recent(self, language: str, *, max_age_hours: int, limit: int) -> list[dict]:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Local backend — a JSON file on disk                                         #
# --------------------------------------------------------------------------- #
class _LocalBackend(_RtiBackend):
    def __init__(self, path: str) -> None:
        self._dir = path
        self._file = os.path.join(path, "news_enriched.json")
        self._lock = asyncio.Lock()

    def _load_sync(self) -> dict[str, dict]:
        if not os.path.exists(self._file):
            return {}
        try:
            with open(self._file, "r", encoding="utf-8") as fh:
                rows = json.load(fh)
            return {r["news_id"]: r for r in rows if r.get("news_id")}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("RTI local store unreadable (%s); starting empty", exc)
            return {}

    def _save_sync(self, data: dict[str, dict]) -> None:
        os.makedirs(self._dir, exist_ok=True)
        tmp = self._file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(list(data.values()), fh, ensure_ascii=False)
        os.replace(tmp, self._file)

    async def ensure_ready(self) -> dict[str, Any]:
        os.makedirs(self._dir, exist_ok=True)
        data = await asyncio.to_thread(self._load_sync)
        return {"status": "ok", "backend": "local", "path": self._file, "count": len(data)}

    async def existing_ids(self, ids: list[str]) -> set[str]:
        async with self._lock:
            data = await asyncio.to_thread(self._load_sync)
        wanted = set(ids)
        return wanted & set(data.keys())

    async def ingest(self, records: list[dict]) -> int:
        if not records:
            return 0
        async with self._lock:
            data = await asyncio.to_thread(self._load_sync)
            for rec in records:
                data[rec["news_id"]] = rec
            await asyncio.to_thread(self._save_sync, data)
        return len(records)

    async def get_by_id(self, news_id: str) -> dict | None:
        async with self._lock:
            data = await asyncio.to_thread(self._load_sync)
        return data.get(news_id)

    async def recent(self, language: str, *, max_age_hours: int, limit: int) -> list[dict]:
        async with self._lock:
            data = await asyncio.to_thread(self._load_sync)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        rows = [r for r in data.values() if r.get("language") == language]
        rows = [r for r in rows if _parse_iso(r.get("seen_at")) >= cutoff]
        rows.sort(key=lambda r: r.get("seen_at") or "", reverse=True)
        return rows[: max(limit, 0) or None]


# --------------------------------------------------------------------------- #
# Eventhouse backend — Fabric KQL database (lazy Kusto SDK import)            #
# --------------------------------------------------------------------------- #
class _EventhouseBackend(_RtiBackend):
    def __init__(self, settings) -> None:  # noqa: ANN001 - Settings
        self._s = settings
        self._table = settings.eventhouse_news_table
        self._db = settings.eventhouse_database
        self._query_client = None
        self._ingest_client = None

    def _clients(self):
        if self._query_client is not None:
            return self._query_client, self._ingest_client
        from azure.identity import DefaultAzureCredential
        from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
        from azure.kusto.ingest import QueuedIngestClient

        cred = DefaultAzureCredential()
        q_kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
            self._s.eventhouse_query_uri, cred
        )
        i_kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
            self._s.eventhouse_ingest_uri or self._s.eventhouse_query_uri, cred
        )
        self._query_client = KustoClient(q_kcsb)
        self._ingest_client = QueuedIngestClient(i_kcsb)
        return self._query_client, self._ingest_client

    def _query_sync(self, kql: str) -> list[dict]:
        client, _ = self._clients()
        resp = client.execute(self._db, kql)
        table = resp.primary_results[0]
        cols = [c.column_name for c in table.columns]
        return [dict(zip(cols, row)) for row in table.rows]

    async def _query(self, kql: str) -> list[dict]:
        return await asyncio.to_thread(self._query_sync, kql)

    def _create_table_sync(self) -> None:
        """Create the enriched-news KQL table if it doesn't already exist.

        ``.create-merge table`` is idempotent — it creates the table or extends
        it with any missing columns, and is a no-op when it already matches.
        """
        client, _ = self._clients()
        cols = ", ".join(f"{name}:{ktype}" for name, ktype in NEWS_COLUMNS)
        client.execute_mgmt(self._db, f".create-merge table ['{self._table}'] ({cols})")

    async def ensure_table(self) -> None:
        await asyncio.to_thread(self._create_table_sync)

    async def ensure_ready(self) -> dict[str, Any]:
        try:
            # Make sure the table exists before counting (first-run provisioning).
            await self.ensure_table()
            rows = await self._query(f"['{self._table}'] | count")
            count = rows[0].get("Count") if rows else None
            return {"status": "ok", "backend": "eventhouse", "database": self._db, "count": count}
        except Exception as exc:  # noqa: BLE001 - report, don't crash startup
            return {"status": "error", "backend": "eventhouse", "detail": str(exc)}

    async def existing_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        id_list = ", ".join(f'"{i}"' for i in ids)
        kql = f"['{self._table}'] | where news_id in ({id_list}) | distinct news_id"
        rows = await self._query(kql)
        return {r["news_id"] for r in rows}

    def _ingest_sync(self, records: list[dict]) -> int:
        import io

        from azure.kusto.data.data_format import DataFormat, IngestionMappingKind
        from azure.kusto.ingest import IngestionProperties

        _, ingest_client = self._clients()
        payload = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in records)
        props = IngestionProperties(
            database=self._db,
            table=self._table,
            data_format=DataFormat.MULTIJSON,
            column_mappings=_json_column_mapping(),
            ingestion_mapping_kind=IngestionMappingKind.JSON,
            flush_immediately=True,
        )
        stream = io.BytesIO(payload.encode("utf-8"))
        ingest_client.ingest_from_stream(stream, ingestion_properties=props)
        return len(records)

    async def ingest(self, records: list[dict]) -> int:
        if not records:
            return 0
        return await asyncio.to_thread(self._ingest_sync, records)

    async def get_by_id(self, news_id: str) -> dict | None:
        kql = f'["{self._table}"] | where news_id == "{news_id}" | top 1 by ingested_at desc'
        rows = await self._query(kql)
        return rows[0] if rows else None

    async def recent(self, language: str, *, max_age_hours: int, limit: int) -> list[dict]:
        kql = (
            f"['{self._table}'] "
            f"| where language == '{language}' "
            f"| where seen_at > ago({max_age_hours}h) "
            f"| summarize arg_max(ingested_at, *) by news_id "
            f"| top {limit} by seen_at desc"
        )
        return await self._query(kql)


def _json_column_mapping():
    """Build a JSON ingestion mapping from :data:`NEWS_COLUMNS`.

    azure-kusto-ingest 6.x: ``ColumnMapping`` takes ``column_name``,
    ``column_type`` and ``path``; the mapping kind is set on
    ``IngestionProperties.ingestion_mapping_kind``.
    """
    from azure.kusto.ingest import ColumnMapping

    return [
        ColumnMapping(column_name=name, column_type=ktype, path=f"$.{name}")
        for name, ktype in NEWS_COLUMNS
    ]


def eventhouse_table_ddl(table: str = "news_enriched") -> str:
    """KQL ``.create table`` statement for the enriched-news table."""
    cols = ", ".join(f"{name}:{ktype}" for name, ktype in NEWS_COLUMNS)
    return f".create table ['{table}'] ({cols})"


# --------------------------------------------------------------------------- #
# Module-level facade                                                          #
# --------------------------------------------------------------------------- #
_backend: _RtiBackend | None = None


def _get_backend() -> _RtiBackend:
    global _backend
    if _backend is None:
        s = get_settings()
        if s.rti_backend.lower() == "eventhouse":
            _backend = _EventhouseBackend(s)
            logger.info("RTI backend: eventhouse (db=%s)", s.eventhouse_database)
        else:
            _backend = _LocalBackend(s.local_rti_path)
            logger.info("RTI backend: local (%s)", s.local_rti_path)
    return _backend


def _parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _coerce_lists(record: dict) -> dict:
    """Ensure list/dynamic fields are real lists (Eventhouse may return JSON)."""
    out = dict(record)
    for field in _LIST_FIELDS | {"embedding"}:
        val = out.get(field)
        if isinstance(val, str):
            try:
                out[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                out[field] = [] if field != "embedding" else None
    return out


async def ensure_ready() -> dict[str, Any]:
    return await _get_backend().ensure_ready()


async def existing_ids(ids: list[str]) -> set[str]:
    return await _get_backend().existing_ids(ids)


async def ingest_news(records: list[dict]) -> int:
    """Upsert enriched news records into the RTI store."""
    return await _get_backend().ingest(records)


async def get_by_id(news_id: str) -> dict | None:
    rec = await _get_backend().get_by_id(news_id)
    return _coerce_lists(rec) if rec else None


async def get_recent(
    language: str,
    *,
    level: str | None = None,
    limit: int = 20,
    max_age_hours: int = 48,
) -> list[dict]:
    """Most-recent enriched articles for a language, optionally near a CEFR level."""
    rows = await _get_backend().recent(language, max_age_hours=max_age_hours, limit=limit * 3)
    rows = [_coerce_lists(r) for r in rows]
    if level:
        rows = [r for r in rows if _within_level(r.get("cefr_level", ""), level)]
    return rows[:limit]


async def search_by_vector(
    language: str,
    query_embedding: list[float],
    *,
    level: str | None = None,
    limit: int = 5,
    max_age_hours: int = 48,
) -> list[dict]:
    """Semantic retrieval: rank recent articles by cosine similarity.

    Falls back to recency when no candidate has an embedding. For the local
    backend the ranking is computed in Python; for Eventhouse it is still
    fetched-then-ranked here so the two backends behave identically.
    """
    candidates = await get_recent(
        language, level=level, limit=max(limit * 6, 30), max_age_hours=max_age_hours
    )
    if not query_embedding:
        return candidates[:limit]

    scored: list[tuple[float, dict]] = []
    for rec in candidates:
        emb = rec.get("embedding")
        if isinstance(emb, list) and emb:
            scored.append((cosine_similarity(query_embedding, emb), rec))
    if not scored:
        return candidates[:limit]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [rec for _, rec in scored[:limit]]
