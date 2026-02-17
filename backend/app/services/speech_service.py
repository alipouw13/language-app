"""
Speech service — Azure Speech SDK integration.

Provides async wrappers around:
  - Speech-to-text (STT)
  - Text-to-speech (TTS)

These are called from the conversation WebSocket handler.
"""

from __future__ import annotations

import io
import logging
from typing import AsyncGenerator

from app.config import get_settings

logger = logging.getLogger(__name__)

# Lazy import — azure-cognitiveservices-speech is an optional heavy dependency.
_speech_sdk = None


def _ensure_sdk():
    global _speech_sdk
    if _speech_sdk is None:
        try:
            import azure.cognitiveservices.speech as speechsdk
            _speech_sdk = speechsdk
        except ImportError:
            raise RuntimeError(
                "azure-cognitiveservices-speech is not installed. "
                "Install it with: pip install azure-cognitiveservices-speech"
            )
    return _speech_sdk


LANGUAGE_VOICE_MAP = {
    "en": "en-US-JennyNeural",
    "fr": "fr-FR-DeniseNeural",
    "es": "es-ES-ElviraNeural",
}

LANGUAGE_LOCALE_MAP = {
    "en": "en-US",
    "fr": "fr-FR",
    "es": "es-ES",
}


def _get_speech_config():
    """Build an Azure Speech config using Entra (DefaultAzureCredential) authentication."""
    speechsdk = _ensure_sdk()
    s = get_settings()
    if not s.azure_speech_endpoint:
        raise ValueError("AZURE_SPEECH_ENDPOINT is not configured")
    
    # Use DefaultAzureCredential for Entra authentication
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:
        raise RuntimeError(
            "azure-identity is not installed. "
            "Install it with: pip install azure-identity"
        )
    
    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    
    # Create speech config with authorization token
    speech_config = speechsdk.SpeechConfig(
        auth_token=token.token,
        region=s.azure_speech_region,
    )
    return speech_config


async def speech_to_text(audio_bytes: bytes, language: str = "en") -> str:
    """Recognise speech from raw WAV/PCM audio bytes.

    Returns the recognised text string.
    """
    speechsdk = _ensure_sdk()
    speech_config = _get_speech_config()
    speech_config.speech_recognition_language = LANGUAGE_LOCALE_MAP.get(language, "en-US")

    # Push stream from bytes
    stream = speechsdk.audio.PushAudioInputStream()
    stream.write(audio_bytes)
    stream.close()

    audio_config = speechsdk.audio.AudioConfig(stream=stream)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        return ""
    else:
        logger.warning("Speech recognition failed: %s", result.reason)
        raise RuntimeError(f"Speech recognition failed: {result.reason}")


async def text_to_speech(text: str, language: str = "en") -> bytes:
    """Synthesise speech from text.

    Returns WAV audio bytes.
    """
    speechsdk = _ensure_sdk()
    speech_config = _get_speech_config()
    voice = LANGUAGE_VOICE_MAP.get(language, "en-US-JennyNeural")
    speech_config.speech_synthesis_voice_name = voice

    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None,  # we'll capture the bytes directly
    )
    result = synthesizer.speak_text(text)

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data
    else:
        logger.warning("Speech synthesis failed: %s", result.reason)
        raise RuntimeError(f"Speech synthesis failed: {result.reason}")
