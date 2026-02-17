"""
Lessons library API routes — paginated access to saved worksheets and conversations.

GET /api/lessons                — paginated lesson list
GET /api/lessons/conversations  — paginated conversation list
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.db_models import Conversation, ConversationTurn, Exercise, Lesson

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("")
async def list_lessons(
    user_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of saved worksheet lessons."""
    base = select(Lesson)
    count_q = select(func.count(Lesson.id))
    if user_id:
        base = base.where(Lesson.user_id == user_id)
        count_q = count_q.where(Lesson.user_id == user_id)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    result = await db.execute(
        base.options(selectinload(Lesson.exercises))
        .order_by(Lesson.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    lessons = result.scalars().all()

    return {
        "items": [
            {
                "id": str(l.id),
                "scenario": l.scenario,
                "target_language": l.target_language,
                "difficulty": l.difficulty,
                "exercise_count": len(l.exercises),
                "created_at": l.created_at.isoformat(),
            }
            for l in lessons
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/conversations")
async def list_conversations(
    user_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of conversation sessions."""
    base = select(Conversation)
    count_q = select(func.count(Conversation.id))
    if user_id:
        base = base.where(Conversation.user_id == user_id)
        count_q = count_q.where(Conversation.user_id == user_id)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    result = await db.execute(
        base.options(selectinload(Conversation.turns))
        .order_by(Conversation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    conversations = result.scalars().all()

    return {
        "items": [
            {
                "id": str(c.id),
                "target_language": c.target_language,
                "scenario_context": c.scenario_context,
                "turn_count": len(c.turns),
                "created_at": c.created_at.isoformat(),
            }
            for c in conversations
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
