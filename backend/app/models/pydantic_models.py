"""
Pydantic request/response schemas.

Kept separate from ORM models so input validation logic
doesn't leak into the persistence layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Worksheet generation
# ---------------------------------------------------------------------------

class WorksheetRequest(BaseModel):
    scenario: str = Field(..., min_length=3, max_length=500)
    target_language: str = Field(..., pattern=r"^(en|fr|es)$")
    grammar_focus: str | None = None
    difficulty: str = Field("A1", pattern=r"^(A1|A2|B1|B2|C1|C2)$")
    user_id: uuid.UUID | None = None


class VocabularyItem(BaseModel):
    word: str
    translation: str
    example_sentence: str


class ExerciseItem(BaseModel):
    type: str  # fill_blank | conjugation | sentence_building | translation
    question: str
    answer: str
    hint: str = ""


class WorksheetResponse(BaseModel):
    scenario_summary: str
    vocabulary: list[VocabularyItem]
    grammar_focus: str
    explanations: str
    exercises: list[ExerciseItem]
    roleplay_prompts: list[str]


class LessonOut(BaseModel):
    id: uuid.UUID
    target_language: str
    scenario: str
    grammar_focus: str | None
    difficulty: str
    worksheet: WorksheetResponse
    version: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Exercise evaluation
# ---------------------------------------------------------------------------

class ExerciseSubmission(BaseModel):
    exercise_id: uuid.UUID
    user_answer: str


class ExerciseEvaluation(BaseModel):
    is_correct: bool
    score: float
    feedback: str
    correct_answer: str


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------

class ConversationStartRequest(BaseModel):
    user_id: uuid.UUID | None = None
    target_language: str = Field(..., pattern=r"^(en|fr|es)$")
    scenario_context: str | None = None


class ConversationMessageRequest(BaseModel):
    text: str = Field(..., min_length=1)


class ConversationTurnOut(BaseModel):
    role: str
    text: str
    corrected_text: str | None = None
    turn_index: int


class ConversationOut(BaseModel):
    id: uuid.UUID
    target_language: str
    scenario_context: str | None
    turns: list[ConversationTurnOut]
    created_at: datetime


# ---------------------------------------------------------------------------
# Lessons library
# ---------------------------------------------------------------------------

class LessonSummary(BaseModel):
    id: uuid.UUID
    scenario: str
    target_language: str
    difficulty: str
    exercise_count: int
    created_at: datetime


class PaginatedLessons(BaseModel):
    items: list[LessonSummary]
    total: int
    page: int
    page_size: int


class ConversationSummary(BaseModel):
    id: uuid.UUID
    target_language: str
    scenario_context: str | None
    turn_count: int
    created_at: datetime


class PaginatedConversations(BaseModel):
    items: list[ConversationSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Simple translation (kept for backward compat)
# ---------------------------------------------------------------------------

class TranslateRequest(BaseModel):
    text: str
    from_lang: str
    to_langs: list[str]


class GrammarRequest(BaseModel):
    sentence: str
    language: str


class ChatRequest(BaseModel):
    history: list[dict[str, str]]
    language: str
