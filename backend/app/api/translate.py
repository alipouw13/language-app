"""
Translation API route — Azure AI Foundry translation model.

POST /api/translate — translate text into one or more target languages.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth.entra import get_principal
from app.models.pydantic_models import TranslationRequest, TranslationResponse
from app.services.translation_service import translate

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/translate",
    tags=["translate"],
    dependencies=[Depends(get_principal)],
)


@router.post("", response_model=TranslationResponse)
async def translate_text(req: TranslationRequest):
    """Translate text using the Foundry translation model (chat-model fallback)."""
    try:
        source, translations, model = await translate(
            req.text, req.source_language, req.target_languages
        )
        return TranslationResponse(
            source_language=source, translations=translations, model=model
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Translation failed")
        raise HTTPException(status_code=500, detail=str(exc))
