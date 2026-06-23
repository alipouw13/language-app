"""
Translation service — Azure AI Foundry translation model.

Demonstrates a dedicated Foundry translation deployment. When
``AZURE_TRANSLATION_MODEL_NAME`` is configured the request is routed to that
deployment on the Foundry endpoint; otherwise it falls back to the main chat
deployment (``app.services.llm_service``) so the feature still works in dev.

Both paths return the same strict-JSON shape, validated before returning.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.services import llm_service

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"en": "English", "fr": "French", "es": "Spanish", "auto": "auto-detect"}

SYSTEM_PROMPT = """\
You are a professional translation engine. Translate the user's text accurately,
preserving meaning, tone and named entities. Respond with a SINGLE JSON object:
{
  "source_language": "<ISO 639-1 code of the detected source language>",
  "translations": { "<target ISO code>": "<translated text>", ... }
}
Use only the requested target language codes as keys. Return ONLY valid JSON."""


def _build_user_prompt(text: str, source_language: str, targets: list[str]) -> str:
    src = LANGUAGE_NAMES.get(source_language, source_language)
    target_desc = ", ".join(f"{t} ({LANGUAGE_NAMES.get(t, t)})" for t in targets)
    src_line = (
        "Detect the source language."
        if source_language == "auto"
        else f"The source language is {src} ({source_language})."
    )
    return (
        f"{src_line}\n"
        f"Translate the following text into: {target_desc}.\n\n"
        f"Text:\n{text}"
    )


async def _translate_with_foundry(model: str, messages: list[dict[str, str]]) -> dict:
    from app.services.foundry import get_foundry_client

    client = get_foundry_client()
    raw = await llm_service.create_chat_completion(
        client,
        model,
        messages,
        temperature=0.0,
        max_tokens=1500,
        json_mode=True,
    )
    return llm_service.parse_json(raw)


async def translate(
    text: str, source_language: str, target_languages: list[str]
) -> tuple[str, dict[str, str], str]:
    """Translate *text* into each target language.

    Returns ``(detected_source_language, {code: translation}, model_used)``.
    """
    settings = get_settings()
    targets = [t for t in target_languages if t in {"en", "fr", "es"}]
    if not targets:
        raise ValueError("No valid target languages provided")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(text, source_language, targets)},
    ]

    model_used: str
    if settings.azure_translation_model_name and settings.azure_foundry_endpoint:
        model_used = settings.azure_translation_model_name
        try:
            data = await _translate_with_foundry(model_used, messages)
        except Exception:
            logger.exception("Foundry translation failed; falling back to chat model")
            model_used = settings.azure_openai_deployment
            data = await llm_service.chat_completion_json(messages, temperature=0.0)
    else:
        model_used = settings.azure_openai_deployment
        data = await llm_service.chat_completion_json(messages, temperature=0.0)

    detected = data.get("source_language") or (
        source_language if source_language != "auto" else "en"
    )
    raw = data.get("translations", {}) or {}
    translations = {code: raw.get(code, "") for code in targets}
    return detected, translations, model_used
