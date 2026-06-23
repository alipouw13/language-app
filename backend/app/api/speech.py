"""
Speech API routes.

POST /api/speech/transcribe — transcribe uploaded audio to text (Foundry STT)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.entra import get_principal
from app.services.speech_service import speech_to_text

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/speech",
    tags=["speech"],
    dependencies=[Depends(get_principal)],
)


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("en"),
):
    """Transcribe an uploaded audio file using the Foundry STT model.

    Accepts common formats (webm, wav, mp3, ogg, mp4). Returns ``{"text": ...}``.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    filename = audio.filename or "audio.webm"
    logger.info(
        "Transcribe request — filename=%s size=%d language=%s",
        filename,
        len(audio_bytes),
        language,
    )
    try:
        text = await speech_to_text(audio_bytes, language, filename=filename)
        return {"text": text}
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=str(exc))
