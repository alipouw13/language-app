"""
Conversation service.

Manages multi-turn conversation sessions persisted as Delta tables in the
Fabric OneLake Lakehouse. Each turn is stored; the last N turns are sent to
the LLM as context for the next reply.
"""

from __future__ import annotations

from app.models.pydantic_models import ConversationStartRequest
from app.repository import store
from app.services import news_service
from app.services.llm_service import chat_completion

LANGUAGE_NAMES = {"en": "English", "fr": "French", "es": "Spanish"}
MEMORY_WINDOW = 10  # number of recent turns sent to the LLM


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
    req: ConversationStartRequest, user_id: str
) -> dict:
    scenario = req.scenario_context
    if req.news_id:
        # Ground the session in a real, current news item (RAG over the RTI hot path).
        scenario = await news_service.build_conversation_context(
            req.news_id, fallback=req.scenario_context
        )
    return await store.create_conversation(
        user_id=user_id,
        target_language=req.target_language,
        scenario_context=scenario,
        news_id=req.news_id,
    )


async def get_conversation(conversation_id: str) -> dict:
    conv = await store.get_conversation(conversation_id)
    if conv is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    return conv


async def add_user_turn_and_reply(
    conversation_id: str, user_text: str
) -> tuple[str, str | None]:
    """Append a user turn, get the LLM reply, append it, and return both.

    Returns ``(reply_text, correction_or_none)``.
    """
    conv = await get_conversation(conversation_id)
    existing_turns = conv["turns"]
    next_index = len(existing_turns)

    user_turn = await store.append_turn(
        conversation_id=conversation_id,
        role="user",
        text=user_text,
        turn_index=next_index,
    )

    system_msg = {
        "role": "system",
        "content": _build_system_prompt(
            conv["target_language"], conv.get("scenario_context")
        ),
    }
    recent = (existing_turns + [user_turn])[-MEMORY_WINDOW:]
    history = [{"role": t["role"], "content": t["text"]} for t in recent]
    messages = [system_msg] + history

    reply_text = await chat_completion(messages, temperature=0.7)

    await store.append_turn(
        conversation_id=conversation_id,
        role="assistant",
        text=reply_text,
        turn_index=next_index + 1,
    )

    correction = reply_text if ("(" in reply_text and ")" in reply_text) else None
    return reply_text, correction
