"""
SQLAlchemy ORM models for the language-learning application.

Tables:
    users            — registered learners
    lessons          — generated worksheet lessons
    exercises        — individual exercises within a lesson
    exercise_attempts— user answers to exercises, scored by LLM
    conversations    — voice/text conversation sessions
    conversation_turns — individual turns inside a conversation
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name = Column(String(120), nullable=False)
    native_language = Column(String(10), nullable=False, default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lessons = relationship("Lesson", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Lessons & exercises
# ---------------------------------------------------------------------------

class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_language = Column(String(10), nullable=False)
    scenario = Column(Text, nullable=False)
    grammar_focus = Column(String(200), nullable=True)
    difficulty = Column(String(4), nullable=False, default="A1")
    worksheet_json = Column(JSONB, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="lessons")
    exercises = relationship("Exercise", back_populates="lesson", cascade="all, delete-orphan")


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    exercise_type = Column(String(30), nullable=False)
    question = Column(Text, nullable=False)
    correct_answer = Column(Text, nullable=False)
    hint = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False, default=0)

    lesson = relationship("Lesson", back_populates="exercises")
    attempts = relationship("ExerciseAttempt", back_populates="exercise", cascade="all, delete-orphan")


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exercise_id = Column(UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user_answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False, default=False)
    llm_feedback = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    exercise = relationship("Exercise", back_populates="attempts")


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_language = Column(String(10), nullable=False)
    scenario_context = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="conversations")
    turns = relationship("ConversationTurn", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationTurn.turn_index")


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(12), nullable=False)  # "user" | "assistant"
    text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=True)  # LLM correction of user text
    turn_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="turns")
