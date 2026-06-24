"""
Application configuration loaded from environment variables.

All secrets and deployment-specific values live in .env (never committed).
Uses pydantic-settings for typed, validated config.

Authentication model
--------------------
Every Azure service uses Microsoft Entra ID (DefaultAzureCredential):
  - Azure OpenAI / Foundry chat, translation and speech models
  - Fabric OneLake (Delta table storage)
The API itself is protected with Entra ID bearer tokens validated against
the tenant JWKS (see app.auth.entra).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env resolved absolutely (config.py is backend/app/config.py), so the
# app and the helper scripts load the same settings no matter the working dir.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Storage — Fabric OneLake Lakehouse (Delta tables)                  #
    # ------------------------------------------------------------------ #
    # "local"   → write Delta tables to LOCAL_LAKEHOUSE_PATH (dev / tests)
    # "onelake" → write Delta tables to a Fabric Lakehouse over abfss
    storage_backend: str = "local"
    local_lakehouse_path: str = "./.lakehouse"

    # Fabric workspace + lakehouse (names or GUIDs both work).
    onelake_workspace: str = ""
    onelake_lakehouse: str = ""
    # OneLake DFS host (rarely changes).
    onelake_host: str = "onelake.dfs.fabric.microsoft.com"
    # Lakehouse schema. Schema-enabled lakehouses store tables under
    # Tables/<schema>/<name> (default schema is "dbo") and only surface those in
    # the UI. Leave empty for a classic (non-schema) lakehouse.
    onelake_schema: str = ""

    # --- Azure OpenAI (chat / evaluation — Entra authentication) ---
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment: str = "gpt-4.1-mini"

    # --- Azure AI Foundry (speech + translation models — Entra auth) ---
    # Base Foundry/Cognitive Services resource endpoint. A trailing
    # "/openai" or "/openai/" is tolerated and stripped automatically.
    azure_foundry_endpoint: str = ""
    azure_foundry_api_version: str = "2025-03-01-preview"

    # Speech model deployment names.
    azure_speech_to_text_model_name: str = "gpt-4o-transcribe"
    azure_text_to_speech_model_name: str = "gpt-4o-mini-tts"

    # Dedicated translation model deployment (optional). When empty the
    # main chat deployment is used as a fallback.
    azure_translation_model_name: str = ""

    # Embedding deployment (optional) used to vectorize news for semantic
    # retrieval. When empty, news retrieval falls back to recency + level only.
    azure_openai_embedding_deployment: str = ""

    # ------------------------------------------------------------------ #
    # Real-Time Intelligence — news stream (Fabric Eventhouse / KQL)     #
    # ------------------------------------------------------------------ #
    # "local"      → enriched news stored on disk (dev / tests, no Fabric)
    # "eventhouse" → enriched news ingested into a Fabric Eventhouse (KQL DB)
    rti_backend: str = "local"
    local_rti_path: str = "./.rti"

    # Fabric Eventhouse (KQL database) — required when rti_backend="eventhouse".
    # The query and ingest URIs come from the Eventhouse "Cluster URI" (https://
    # <cluster>.kusto.fabric.microsoft.com); ingest URI is usually the same host.
    eventhouse_query_uri: str = ""
    eventhouse_ingest_uri: str = ""
    eventhouse_database: str = ""
    # KQL table that holds enriched news records.
    eventhouse_news_table: str = "news_enriched"

    # --- GDELT news source ---
    # Languages to ingest current-events news for (subset of en/fr/es).
    news_languages: list[str] = ["es", "fr"]
    # How far back GDELT looks per poll, and the cap on articles per language.
    gdelt_timespan: str = "1d"
    gdelt_max_records: int = 40
    # Optional per-language GDELT query override (empty → built-in defaults).
    gdelt_query_es: str = ""
    gdelt_query_fr: str = ""
    gdelt_query_en: str = ""

    # CEFR level assumed for a learner when none is known (affects grading).
    news_default_level: str = "B1"
    # Discard enriched news older than this many hours when serving topics.
    news_max_age_hours: int = 48

    # Background poller: when enabled the API ingests news on a timer.
    news_poll_enabled: bool = False
    news_poll_interval_minutes: int = 60

    # ------------------------------------------------------------------ #
    # API authentication — Microsoft Entra ID                            #
    # ------------------------------------------------------------------ #
    # When enabled, every /api route requires a valid Entra ID bearer token.
    entra_auth_enabled: bool = False
    entra_tenant_id: str = ""
    # The Application ID URI / client ID this API expects as the token audience.
    entra_api_audience: str = ""
    # Accepted token audiences may be the client id and/or api://<client-id>.
    entra_additional_audiences: list[str] = []

    # --- App ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: str = "INFO"

    # ------------------------------------------------------------------ #
    # Derived helpers                                                    #
    # ------------------------------------------------------------------ #
    @property
    def foundry_endpoint_base(self) -> str:
        """Foundry endpoint normalised to the resource root (no /openai)."""
        ep = self.azure_foundry_endpoint.rstrip("/")
        if ep.endswith("/openai"):
            ep = ep[: -len("/openai")]
        return ep

    @property
    def onelake_tables_uri(self) -> str:
        """abfss base URI for the Lakehouse 'Tables' area.

        OneLake accepts either GUIDs or friendly names. A friendly lakehouse
        name takes a ``.Lakehouse`` item-type suffix, but a GUID must be used
        bare (appending the suffix triggers ``FriendlyNameSupportDisabled``).
        """
        import re

        guid_re = re.compile(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
        lakehouse = self.onelake_lakehouse
        if (
            lakehouse
            and not guid_re.match(lakehouse)
            and not lakehouse.lower().endswith(".lakehouse")
        ):
            lakehouse = f"{lakehouse}.Lakehouse"
        return (
            f"abfss://{self.onelake_workspace}@{self.onelake_host}/"
            f"{lakehouse}/Tables"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
