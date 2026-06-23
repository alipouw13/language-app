"""
Centralized LLM client.

Wraps Azure OpenAI / Foundry chat completions. Every LLM interaction in the
application routes through this module so that model selection, parameter
handling, and retry logic live in one place.

Different deployments accept different parameters:

* Older models (e.g. ``gpt-4.1-mini``) use ``max_tokens`` and accept a custom
  ``temperature``.
* Newer reasoning-style models (e.g. ``gpt-5.x``) require ``max_completion_tokens``
  and only allow the default ``temperature`` (1.0).

Rather than hard-coding model families, the client sends the modern parameters
first and *adapts* on a 400 "unsupported parameter" response — swapping
``max_tokens`` ↔ ``max_completion_tokens`` and dropping an unsupported
``temperature``. What works for each model is cached so the adaptation only
costs one failed call per deployment.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI, BadRequestError

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncAzureOpenAI | None = None

# Per-model learned capabilities, keyed by deployment name:
#   "token_param" -> "max_completion_tokens" | "max_tokens"
#   "temperature" -> True (custom allowed) | False (default only)
_model_caps: dict[str, dict[str, Any]] = {}


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


async def create_chat_completion(
    client: AsyncAzureOpenAI,
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    json_mode: bool = False,
) -> str:
    """Create a chat completion, adapting parameters to the deployment.

    Works against any AsyncAzureOpenAI client (main chat or Foundry) so callers
    share one resilient implementation. Returns the assistant message content.
    """
    caps = _model_caps.setdefault(
        model, {"token_param": "max_completion_tokens", "temperature": True}
    )

    response = None
    # Retry loop: at most a few attempts while we learn what the model rejects.
    for _ in range(4):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            caps["token_param"]: max_tokens,
        }
        if caps["temperature"]:
            kwargs["temperature"] = temperature
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**kwargs)
            break
        except BadRequestError as exc:
            param = _unsupported_param(exc)
            if param in ("max_tokens", "max_completion_tokens"):
                # Swap to the other token parameter and retry.
                caps["token_param"] = (
                    "max_completion_tokens"
                    if caps["token_param"] == "max_tokens"
                    else "max_tokens"
                )
                logger.info("Model %s: using %s", model, caps["token_param"])
                continue
            if param == "temperature" and caps["temperature"]:
                caps["temperature"] = False
                logger.info("Model %s: temperature not supported, using default", model)
                continue
            raise

    if response is None:
        raise RuntimeError(f"Could not satisfy parameter requirements for model {model}")

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("LLM returned empty content")
    return content.strip()


def _unsupported_param(exc: BadRequestError) -> str | None:
    """Extract the offending parameter name from an OpenAI 400 error.

    Tolerates both body shapes ({"error": {...}} or a bare error dict) and
    falls back to scanning the message text.
    """
    param = None
    msg = ""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        param = err.get("param")
        msg = err.get("message", "") or ""
    if not msg:
        msg = str(exc)

    if param in ("max_tokens", "max_completion_tokens", "temperature"):
        return param

    msg_l = msg.lower()
    if "max_completion_tokens" in msg_l:
        return "max_completion_tokens"
    if "max_tokens" in msg_l:
        return "max_tokens"
    if "temperature" in msg_l:
        return "temperature"
    return None


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    json_mode: bool = False,
) -> str:
    """Send a chat completion request to the main chat deployment."""
    s = get_settings()
    return await create_chat_completion(
        _get_client(),
        s.azure_openai_deployment,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=json_mode,
    )


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
    return parse_json(raw)


def parse_json(raw: str) -> dict[str, Any]:
    """Parse model output as JSON, tolerating markdown code fences."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            inner = cleaned.split("```", 2)
            if len(inner) >= 2:
                body = inner[1]
                if body.lstrip().lower().startswith("json"):
                    body = body.lstrip()[4:]
                try:
                    return json.loads(body.strip("` \n"))
                except json.JSONDecodeError:
                    pass
        logger.error("LLM returned invalid JSON: %s", raw[:500])
        raise ValueError("LLM returned invalid JSON")
