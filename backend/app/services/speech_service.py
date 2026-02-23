"""
Speech service — Azure AI Foundry (OpenAI-compatible) integration.

Provides async wrappers around:
  - Speech-to-text (STT) via gpt-4o-transcribe-diarize
  - Text-to-speech (TTS) via gpt-4o-mini-tts

Uses Entra ID (DefaultAzureCredential) for authentication — key auth is
not supported.

These are called from the conversation WebSocket handler.
"""

from __future__ import annotations

import io
import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

# Language → voice mapping for TTS (OpenAI voice names)
LANGUAGE_VOICE_MAP = {
    "en": "alloy",
    "fr": "nova",
    "es": "shimmer",
}

LANGUAGE_LOCALE_MAP = {
    "en": "en",
    "fr": "fr",
    "es": "es",
}

# Module-level cached client
_client: AzureOpenAI | None = None


def _get_client() -> AzureOpenAI:
    """Return (and cache) an AzureOpenAI client authenticated via Entra ID."""
    global _client
    if _client is not None:
        return _client

    s = get_settings()
    if not s.azure_foundry_endpoint:
        raise ValueError("AZURE_FOUNDRY_ENDPOINT is not configured")

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    _client = AzureOpenAI(
        azure_endpoint=s.azure_foundry_endpoint.rstrip("/"),
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview",
    )
    return _client


async def speech_to_text(audio_bytes: bytes, language: str = "en") -> str:
    """Transcribe speech from audio bytes using gpt-4o-transcribe-diarize.

    Returns the recognised text string.
    """
    s = get_settings()
    client = _get_client()
    locale = LANGUAGE_LOCALE_MAP.get(language, "en")

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.wav"

    logger.info("STT request — model=%s language=%s", s.azure_speech_to_text_model_name, locale)

    transcription = client.audio.transcriptions.create(
        model=s.azure_speech_to_text_model_name,
        file=audio_file,
        language=locale,
    )

    text = transcription.text or ""
    logger.info("STT result: %s", text[:120])
    return text


async def text_to_speech(text: str, language: str = "en") -> bytes:
    """Synthesise speech from text using gpt-4o-mini-tts.

    Returns audio bytes (mp3).
    """
    s = get_settings()
    client = _get_client()
    voice = LANGUAGE_VOICE_MAP.get(language, "alloy")

    logger.info("TTS request — model=%s voice=%s", s.azure_text_to_speech_model_name, voice)

    response = client.audio.speech.create(
        model=s.azure_text_to_speech_model_name,
        voice=voice,
        input=text,
    )

    audio_data = response.content
    logger.info("TTS result: %d bytes", len(audio_data))
    return audio_data
