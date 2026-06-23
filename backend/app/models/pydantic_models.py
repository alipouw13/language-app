"""
Pydantic request/response schemas.

Kept separate from the persistence layer so input validation logic doesn't
leak into the data store. Caller identity comes from the Entra principal
(see app.auth.entra), so requests no longer carry a ``user_id``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

LANG_PATTERN = r"^(en|fr|es)$"
LEVEL_PATTERN = r"^(A1|A2|B1|B2|C1|C2)$"


# --------------------------------------------------------------------------- #
# Worksheet generation                                                         #
# --------------------------------------------------------------------------- #
class WorksheetRequest(BaseModel):
    scenario: str = Field(..., min_length=3, max_length=500)
    target_language: str = Field(..., pattern=LANG_PATTERN)
    grammar_focus: str | None = None
    difficulty: str = Field("A1", pattern=LEVEL_PATTERN)


class VerbWorksheetRequest(BaseModel):
    """Request a worksheet focused on a single verb."""

    verb: str = Field(..., min_length=1, max_length=80)
    target_language: str = Field(..., pattern=LANG_PATTERN)
    native_language: str = Field("en", pattern=LANG_PATTERN)
    grammar_focus: str | None = None  # specific tense (optional)
    difficulty: str = Field("A2", pattern=LEVEL_PATTERN)


class VocabularyItem(BaseModel):
    word: str
    translation: str
    example_sentence: str


class ConjugationRow(BaseModel):
    pronoun: str
    form: str
    translation: str = ""


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
    # Verb-practice extras (optional; populated in verb mode).
    verb: str | None = None
    conjugation_table: list[ConjugationRow] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Exercise evaluation                                                          #
# --------------------------------------------------------------------------- #
class ExerciseSubmission(BaseModel):
    exercise_id: str
    user_answer: str


class ExerciseEvaluation(BaseModel):
    is_correct: bool
    score: float
    feedback: str
    correct_answer: str


# --------------------------------------------------------------------------- #
# Translation (Foundry translation model)                                      #
# --------------------------------------------------------------------------- #
class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    source_language: str = Field("auto", pattern=r"^(auto|en|fr|es)$")
    target_languages: list[str] = Field(..., min_length=1)


class TranslationResponse(BaseModel):
    source_language: str
    translations: dict[str, str]
    model: str


# --------------------------------------------------------------------------- #
# Speech (text-to-speech)                                                      #
# --------------------------------------------------------------------------- #
class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    language: str = Field("en", pattern=LANG_PATTERN)


# --------------------------------------------------------------------------- #
# Conversation                                                                 #
# --------------------------------------------------------------------------- #
class ConversationStartRequest(BaseModel):
    target_language: str = Field(..., pattern=LANG_PATTERN)
    scenario_context: str | None = None


class ConversationMessageRequest(BaseModel):
    text: str = Field(..., min_length=1)


class ConversationTurnOut(BaseModel):
    role: str
    text: str
    corrected_text: str | None = None
    turn_index: int


# --------------------------------------------------------------------------- #
# Lessons library                                                              #
# --------------------------------------------------------------------------- #
class LessonSummary(BaseModel):
    id: str
    scenario: str
    target_language: str
    difficulty: str
    mode: str = "scenario"
    verb: str | None = None
    exercise_count: int
    created_at: datetime


class ConversationSummary(BaseModel):
    id: str
    target_language: str
    scenario_context: str | None
    turn_count: int
    created_at: datetime


class PaginatedLessons(BaseModel):
    items: list[LessonSummary]
    total: int
    page: int
    page_size: int


class PaginatedConversations(BaseModel):
    items: list[ConversationSummary]
    total: int
    page: int
    page_size: int
