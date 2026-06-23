"""
Speech service — Azure AI Foundry (OpenAI-compatible) integration.

Async wrappers around:
  - Speech-to-text (STT) via a transcription deployment (default
    ``gpt-4o-transcribe``)
  - Text-to-speech (TTS) via a TTS deployment (default ``gpt-4o-mini-tts``)

Authentication is Microsoft Entra ID (DefaultAzureCredential) through the
shared Foundry client. The previous implementation failed because:
  * the configured endpoint ended in ``/openai`` and the SDK appended another
    ``/openai`` segment (404), now normalised in config; and
  * a synchronous client was used inside async handlers.
"""

from __future__ import annotations

import io
import logging

from app.config import get_settings
from app.services.foundry import get_foundry_client

logger = logging.getLogger(__name__)

# Language → OpenAI voice mapping for TTS.
LANGUAGE_VOICE_MAP = {"en": "alloy", "fr": "nova", "es": "shimmer"}
LANGUAGE_LOCALE_MAP = {"en": "en", "fr": "fr", "es": "es"}


async def speech_to_text(
    audio_bytes: bytes,
    language: str = "en",
    filename: str = "audio.webm",
) -> str:
    """Transcribe audio bytes to text.

    *filename* tells the API the container format (e.g. ``audio.webm``,
    ``audio.wav``, ``audio.mp3``). Returns the recognised text.
    """
    s = get_settings()
    if not s.azure_speech_to_text_model_name:
        raise ValueError("AZURE_SPEECH_TO_TEXT_MODEL_NAME is not configured")

    client = get_foundry_client()
    locale = LANGUAGE_LOCALE_MAP.get(language, "en")

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    logger.info(
        "STT request — model=%s language=%s bytes=%d",
        s.azure_speech_to_text_model_name,
        locale,
        len(audio_bytes),
    )

    transcription = await client.audio.transcriptions.create(
        model=s.azure_speech_to_text_model_name,
        file=audio_file,
        language=locale,
    )

    text = getattr(transcription, "text", "") or ""
    logger.info("STT result: %s", text[:120])
    return text


async def text_to_speech(text: str, language: str = "en") -> bytes:
    """Synthesise speech (mp3 bytes) from *text*."""
    s = get_settings()
    if not s.azure_text_to_speech_model_name:
        raise ValueError("AZURE_TEXT_TO_SPEECH_MODEL_NAME is not configured")

    client = get_foundry_client()
    voice = LANGUAGE_VOICE_MAP.get(language, "alloy")

    logger.info(
        "TTS request — model=%s voice=%s", s.azure_text_to_speech_model_name, voice
    )

    response = await client.audio.speech.create(
        model=s.azure_text_to_speech_model_name,
        voice=voice,
        input=text,
    )
    audio_data = response.content
    logger.info("TTS result: %d bytes", len(audio_data))
    return audio_data
