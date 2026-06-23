"""
Shared Azure AI Foundry client.

A single cached ``AsyncAzureOpenAI`` instance pointed at the Foundry resource,
authenticated with Microsoft Entra ID (DefaultAzureCredential). Used for the
translation, speech-to-text and text-to-speech model deployments.

The Foundry endpoint is normalised in config so a trailing ``/openai`` does not
produce a malformed ``/openai/openai`` URL.
"""

from __future__ import annotations

import logging

from openai import AsyncAzureOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncAzureOpenAI | None = None


def get_foundry_client() -> AsyncAzureOpenAI:
    """Return (and cache) the Entra-authenticated Foundry client."""
    global _client
    if _client is not None:
        return _client

    s = get_settings()
    if not s.azure_foundry_endpoint:
        raise ValueError("AZURE_FOUNDRY_ENDPOINT is not configured")

    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    _client = AsyncAzureOpenAI(
        azure_endpoint=s.foundry_endpoint_base,
        azure_ad_token_provider=token_provider,
        api_version=s.azure_foundry_api_version,
    )
    logger.info("Foundry client initialised (endpoint=%s)", s.foundry_endpoint_base)
    return _client
