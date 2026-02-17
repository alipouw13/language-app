"""
Centralized LLM client.

Wraps Azure OpenAI chat completions. Every LLM interaction in the
application routes through this module so that model, temperature, and
retry logic live in one place.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncAzureOpenAI | None = None


def _get_client() -> AsyncAzureOpenAI:
    global _client
    if _client is None:
        s = get_settings()
        # Use Entra authentication (API keys are disabled on this resource)
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        _client = AsyncAzureOpenAI(
            azure_ad_token_provider=token_provider,
            api_version=s.azure_openai_api_version,
            azure_endpoint=s.azure_openai_endpoint,
        )
    return _client


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    json_mode: bool = False,
) -> str:
    """Send a chat completion request and return the assistant content."""
    client = _get_client()
    s = get_settings()

    kwargs: dict[str, Any] = dict(
        model=s.azure_openai_deployment,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("LLM returned empty content")
    return content.strip()


async def chat_completion_json(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Chat completion that parses the response as JSON.

    Uses JSON mode when available and validates the output.
    """
    raw = await chat_completion(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s", raw[:500])
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
