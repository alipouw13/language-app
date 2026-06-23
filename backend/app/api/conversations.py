"""
Conversation API routes.

POST /api/conversations                  — start a new session
POST /api/conversations/{id}/message     — send a text message
GET  /api/conversations/{id}             — retrieve full transcript
WS   /api/conversations/{id}/ws          — WebSocket for voice/text streaming
"""

from __future__ import annotations

import base64
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.auth.entra import Principal, authenticate_ws, get_principal
from app.models.pydantic_models import (
    ConversationMessageRequest,
    ConversationStartRequest,
)
from app.repository import store
from app.services.conversation_service import (
    add_user_turn_and_reply,
    get_conversation,
    start_conversation,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/conversations",
    tags=["conversations"],
    dependencies=[Depends(get_principal)],
)


@router.post("", response_model=dict)
async def create_conversation(
    req: ConversationStartRequest,
    principal: Principal = Depends(get_principal),
):
    """Start a new conversation session."""
    user_id = await store.get_or_create_user(principal.id, display_name=principal.name or "Learner")
    conv = await start_conversation(req, user_id)
    return {
        "id": conv["id"],
        "target_language": conv["target_language"],
        "scenario_context": conv["scenario_context"],
    }


@router.post("/{conversation_id}/message")
async def send_message(
    conversation_id: str,
    req: ConversationMessageRequest,
):
    """Send a text message and receive the AI reply."""
    try:
        reply, correction = await add_user_turn_and_reply(conversation_id, req.text)
        return {"reply": reply, "correction": correction}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Conversation error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{conversation_id}")
async def get_conversation_detail(conversation_id: str):
    """Get the full conversation transcript."""
    try:
        conv = await get_conversation(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "id": conv["id"],
        "target_language": conv["target_language"],
        "scenario_context": conv["scenario_context"],
        "created_at": conv["created_at"],
        "turns": [
            {
                "role": t["role"],
                "text": t["text"],
                "corrected_text": t.get("corrected_text"),
                "turn_index": t["turn_index"],
            }
            for t in conv["turns"]
        ],
    }


@router.websocket("/{conversation_id}/ws")
async def conversation_websocket(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for voice/text conversation streaming.

    Authentication: pass the Entra access token as the ``token`` query
    parameter (``?token=<jwt>``). Skipped when auth is disabled.

    Protocol:
      Client → Server:
        {"type": "audio", "data": "<base64>", "language": "fr"}
        {"type": "text",  "data": "Bonjour!", "language": "fr"}
      Server → Client:
        {"type": "transcript", "text": "..."}
        {"type": "reply", "text": "...", "audio": "<base64-mp3>"}
        {"type": "error", "message": "..."}
    """
    token = websocket.query_params.get("token")
    try:
        authenticate_ws(token)
    except HTTPException:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "text")
            language = msg.get("language", "en")

            try:
                if msg_type == "audio":
                    from app.services.speech_service import speech_to_text, text_to_speech

                    audio_bytes = base64.b64decode(msg["data"])
                    transcript = await speech_to_text(audio_bytes, language)
                    await websocket.send_json({"type": "transcript", "text": transcript})

                    if transcript:
                        reply, _ = await add_user_turn_and_reply(conversation_id, transcript)
                        response = {"type": "reply", "text": reply}
                        try:
                            audio_out = await text_to_speech(reply, language)
                            response["audio"] = base64.b64encode(audio_out).decode()
                        except Exception:
                            logger.warning("TTS failed; sending text-only reply")
                        await websocket.send_json(response)

                elif msg_type == "text":
                    text = msg.get("data", "")
                    if text:
                        reply, _ = await add_user_turn_and_reply(conversation_id, text)
                        response = {"type": "reply", "text": reply}
                        try:
                            from app.services.speech_service import text_to_speech

                            audio_out = await text_to_speech(reply, language)
                            response["audio"] = base64.b64encode(audio_out).decode()
                        except Exception:
                            pass
                        await websocket.send_json(response)

            except Exception as exc:
                logger.exception("WS processing error")
                await websocket.send_json({"type": "error", "message": str(exc)})

    except WebSocketDisconnect:
        logger.info("Client disconnected from conversation %s", conversation_id)
