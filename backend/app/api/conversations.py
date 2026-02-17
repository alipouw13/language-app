"""
Conversation API routes.

POST /api/conversations                  — start a new session
POST /api/conversations/{id}/message     — send a text message
GET  /api/conversations/{id}             — retrieve full transcript
WS   /api/conversations/{id}/ws          — WebSocket for voice streaming
"""

from __future__ import annotations

import base64
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, async_session
from app.models.pydantic_models import (
    ConversationMessageRequest,
    ConversationOut,
    ConversationStartRequest,
    ConversationTurnOut,
)
from app.services.conversation_service import (
    add_user_turn_and_reply,
    get_conversation,
    start_conversation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=dict)
async def create_conversation(
    req: ConversationStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start a new conversation session."""
    conv = await start_conversation(req, db)
    return {
        "id": str(conv.id),
        "target_language": conv.target_language,
        "scenario_context": conv.scenario_context,
    }


@router.post("/{conversation_id}/message")
async def send_message(
    conversation_id: uuid.UUID,
    req: ConversationMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a text message and receive the AI reply."""
    try:
        reply, correction = await add_user_turn_and_reply(conversation_id, req.text, db)
        return {"reply": reply, "correction": correction}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Conversation error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{conversation_id}")
async def get_conversation_detail(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full conversation transcript."""
    try:
        conv = await get_conversation(conversation_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "id": str(conv.id),
        "target_language": conv.target_language,
        "scenario_context": conv.scenario_context,
        "created_at": conv.created_at.isoformat(),
        "turns": [
            {
                "role": t.role,
                "text": t.text,
                "corrected_text": t.corrected_text,
                "turn_index": t.turn_index,
            }
            for t in conv.turns
        ],
    }


@router.websocket("/{conversation_id}/ws")
async def conversation_websocket(websocket: WebSocket, conversation_id: uuid.UUID):
    """WebSocket endpoint for voice conversation streaming.

    Protocol:
      Client → Server:
        {"type": "audio", "data": "<base64-wav>", "language": "fr"}
        {"type": "text", "data": "Bonjour!", "language": "fr"}
      Server → Client:
        {"type": "transcript", "text": "..."}
        {"type": "reply", "text": "...", "audio": "<base64-wav>"}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "text")
            language = msg.get("language", "en")

            async with async_session() as db:
                try:
                    if msg_type == "audio":
                        # Decode audio, run STT, then treat as text
                        from app.services.speech_service import speech_to_text, text_to_speech

                        audio_bytes = base64.b64decode(msg["data"])
                        transcript = await speech_to_text(audio_bytes, language)
                        await websocket.send_json({"type": "transcript", "text": transcript})

                        if transcript:
                            reply, _ = await add_user_turn_and_reply(conversation_id, transcript, db)
                            await db.commit()

                            # Synthesise reply audio
                            try:
                                audio_out = await text_to_speech(reply, language)
                                audio_b64 = base64.b64encode(audio_out).decode()
                            except Exception:
                                audio_b64 = None

                            response = {"type": "reply", "text": reply}
                            if audio_b64:
                                response["audio"] = audio_b64
                            await websocket.send_json(response)

                    elif msg_type == "text":
                        text = msg.get("data", "")
                        if text:
                            reply, _ = await add_user_turn_and_reply(conversation_id, text, db)
                            await db.commit()

                            # Optionally synthesise TTS
                            audio_b64 = None
                            try:
                                from app.services.speech_service import text_to_speech
                                audio_out = await text_to_speech(reply, language)
                                audio_b64 = base64.b64encode(audio_out).decode()
                            except Exception:
                                pass

                            response = {"type": "reply", "text": reply}
                            if audio_b64:
                                response["audio"] = audio_b64
                            await websocket.send_json(response)

                except Exception as exc:
                    logger.exception("WS processing error")
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    await db.rollback()

    except WebSocketDisconnect:
        logger.info("Client disconnected from conversation %s", conversation_id)
