"""
Conversation service.

Manages multi-turn conversation sessions backed by PostgreSQL.
Each turn is stored, and the last N turns are sent to the LLM
as context for the next reply.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import Conversation, ConversationTurn
from app.models.pydantic_models import ConversationStartRequest
from app.services.llm_service import chat_completion

LANGUAGE_NAMES = {"en": "English", "fr": "French", "es": "Spanish"}
MEMORY_WINDOW = 10  # number of recent turns sent to LLM


def _build_system_prompt(language: str, scenario: str | None) -> str:
    lang_name = LANGUAGE_NAMES.get(language, language)
    base = (
        f"You are a friendly language tutor having a natural conversation in {lang_name}. "
        f"Stay in {lang_name} at all times. Keep responses to 2-4 sentences. "
        f"When the user makes grammar or verb-tense mistakes, gently provide the corrected "
        f"phrasing in parentheses — but do not break conversational immersion. "
        f"Ask follow-up questions to keep the dialogue flowing."
    )
    if scenario:
        base += f"\n\nConversation scenario: {scenario}"
    return base


async def start_conversation(
    req: ConversationStartRequest,
    db: AsyncSession,
) -> Conversation:
    """Create a new conversation session."""
    user_id = req.user_id or uuid.uuid4()
    conv = Conversation(
        user_id=user_id,
        target_language=req.target_language,
        scenario_context=req.scenario_context,
    )
    db.add(conv)
    await db.flush()
    return conv


async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession,
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.turns))
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    return conv


async def add_user_turn_and_reply(
    conversation_id: uuid.UUID,
    user_text: str,
    db: AsyncSession,
) -> tuple[str, str | None]:
    """Append a user turn, get LLM reply, return (reply_text, correction_or_none).

    The correction is the LLM's inline-corrected version of the user's text,
    or None if no correction was needed.
    """
    conv = await get_conversation(conversation_id, db)

    next_index = len(conv.turns)

    # Store user turn
    user_turn = ConversationTurn(
        conversation_id=conv.id,
        role="user",
        text=user_text,
        turn_index=next_index,
    )
    db.add(user_turn)
    await db.flush()

    # Build LLM messages from recent history
    system_msg = {
        "role": "system",
        "content": _build_system_prompt(conv.target_language, conv.scenario_context),
    }
    history_msgs = []
    recent_turns = conv.turns[-(MEMORY_WINDOW):]  # last N turns
    for t in recent_turns:
        history_msgs.append({"role": t.role, "content": t.text})
    # Append current user message
    history_msgs.append({"role": "user", "content": user_text})

    messages = [system_msg] + history_msgs

    reply_text = await chat_completion(messages, temperature=0.7)

    # Store assistant turn
    assistant_turn = ConversationTurn(
        conversation_id=conv.id,
        role="assistant",
        text=reply_text,
        turn_index=next_index + 1,
    )
    db.add(assistant_turn)
    await db.flush()

    # Detect inline corrections (simple heuristic: parenthesized corrections)
    correction = None
    if "(" in reply_text and ")" in reply_text:
        correction = reply_text  # full reply contains inline corrections

    return reply_text, correction
