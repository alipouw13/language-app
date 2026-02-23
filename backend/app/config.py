"""
Application configuration loaded from environment variables.

All secrets and deployment-specific values live in .env (never committed).
Uses pydantic-settings for typed, validated config.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/language_app"

    # --- Azure OpenAI ---
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment: str = "gpt-4"

    # --- Azure Speech Services (Entra authentication only) ---
    azure_speech_endpoint: str = ""
    azure_speech_region: str = "eastus"

    # --- Azure AI Foundry (speech model endpoints — Entra auth only) ---
    azure_foundry_endpoint: str = ""
    azure_speech_to_text_model_name: str = ""
    azure_text_to_speech_model_name: str = ""

    # --- Azure PostgreSQL (for auto-start & firewall management) ---
    azure_pg_resource_group: str = ""
    azure_pg_server_name: str = ""

    # --- App ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
