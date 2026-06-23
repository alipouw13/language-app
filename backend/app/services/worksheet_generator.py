"""
Worksheet generation service.

Builds a structured prompt, calls the LLM in strict JSON mode, validates the
response, and persists the resulting lesson + exercises to the Fabric OneLake
Lakehouse store.

Two modes:
  * ``scenario`` — a real-life situation worksheet (optionally tense-focused).
  * ``verb`` — focused on a single verb: its translations, conjugations and
    use in real sentences / conversations.
"""

from __future__ import annotations

import logging

from app.models.pydantic_models import (
    VerbWorksheetRequest,
    WorksheetRequest,
    WorksheetResponse,
)
from app.repository import store
from app.services.llm_service import chat_completion_json

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"en": "English", "fr": "French", "es": "Spanish"}

# --------------------------------------------------------------------------- #
# Scenario worksheets                                                          #
# --------------------------------------------------------------------------- #
SCENARIO_SYSTEM_PROMPT = """\
You are an expert language teacher and curriculum designer.
Generate a structured worksheet as a SINGLE JSON object.

The JSON MUST contain exactly these keys:
- scenario_summary (string): 2-3 sentence overview of the scenario
- vocabulary (array of objects with word, translation, example_sentence)
- grammar_focus (string): the primary grammar topic covered (MUST match the requested verb tense/grammar if provided)
- explanations (string): clear, beginner-friendly grammar explanation focusing on the specified tense/grammar topic
- exercises (array of objects with type, question, answer, hint)
  type must be one of: fill_blank, conjugation, sentence_building, translation
- roleplay_prompts (array of strings): 3-5 conversation starters for practice

IMPORTANT: If a specific verb tense or grammar topic is requested, ALL exercises MUST focus on that tense.
The explanations MUST thoroughly cover the requested grammar topic with conjugation tables if applicable.
Include 8-12 vocabulary items and 6-10 exercises.
Return ONLY valid JSON. No markdown, no code fences."""


def _scenario_user_prompt(req: WorksheetRequest) -> str:
    lang = LANGUAGE_NAMES.get(req.target_language, req.target_language)
    parts = [
        f'Create a {lang} language worksheet for the scenario: "{req.scenario}".',
        f"Difficulty level: {req.difficulty} (CEFR).",
    ]
    if req.grammar_focus:
        parts.append(
            f"REQUIRED GRAMMAR FOCUS: {req.grammar_focus}. "
            f"All exercises must practice this specific tense/grammar topic."
        )
    parts.append("Ensure exercises test both comprehension and production.")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Verb worksheets                                                              #
# --------------------------------------------------------------------------- #
VERB_SYSTEM_PROMPT = """\
You are an expert language teacher specialising in verb mastery.
Generate a worksheet focused on a SINGLE verb, as a SINGLE JSON object.

The JSON MUST contain exactly these keys:
- scenario_summary (string): 2-3 sentences on the verb's meaning(s) and when it is used
- verb (string): the target-language infinitive being practised
- conjugation_table (array of objects with pronoun, form, translation): full
  conjugation for the requested tense (or the present tense if none specified)
- vocabulary (array of objects with word, translation, example_sentence):
  8-10 collocations, expressions or related words that commonly appear with the verb
- grammar_focus (string): the tense/grammar being practised
- explanations (string): how the verb conjugates and behaves, including irregularities
- exercises (array of objects with type, question, answer, hint): 8-10 items.
  EMPHASISE translation in BOTH directions and using the verb in real sentences:
    * at least 4 'translation' exercises (translate a full natural sentence that
      uses the verb, between {native} and {target})
    * at least 2 'conjugation' exercises
    * at least 2 'sentence_building' exercises that place the verb in a realistic
      conversational context
  type must be one of: fill_blank, conjugation, sentence_building, translation
- roleplay_prompts (array of strings): 3-5 real conversation prompts where the
  learner must naturally use the verb

Return ONLY valid JSON. No markdown, no code fences."""


def _verb_user_prompt(req: VerbWorksheetRequest) -> str:
    target = LANGUAGE_NAMES.get(req.target_language, req.target_language)
    native = LANGUAGE_NAMES.get(req.native_language, req.native_language)
    parts = [
        f'Create a {target} worksheet to master the verb "{req.verb}".',
        f"The learner's native language is {native}; translation exercises go "
        f"both {native}↔{target}.",
        f"Difficulty level: {req.difficulty} (CEFR).",
    ]
    if req.grammar_focus:
        parts.append(f"Focus the conjugation and exercises on the {req.grammar_focus} tense.")
    else:
        parts.append("Use the present tense unless a more natural default applies.")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Generation                                                                   #
# --------------------------------------------------------------------------- #
async def generate_worksheet(req: WorksheetRequest) -> WorksheetResponse:
    messages = [
        {"role": "system", "content": SCENARIO_SYSTEM_PROMPT},
        {"role": "user", "content": _scenario_user_prompt(req)},
    ]
    data = await chat_completion_json(messages, temperature=0.4, max_tokens=4096)
    return WorksheetResponse(**data)


async def generate_verb_worksheet(req: VerbWorksheetRequest) -> WorksheetResponse:
    system = VERB_SYSTEM_PROMPT.format(
        native=LANGUAGE_NAMES.get(req.native_language, req.native_language),
        target=LANGUAGE_NAMES.get(req.target_language, req.target_language),
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": _verb_user_prompt(req)},
    ]
    data = await chat_completion_json(messages, temperature=0.4, max_tokens=4096)
    data.setdefault("verb", req.verb)
    return WorksheetResponse(**data)


# --------------------------------------------------------------------------- #
# Persistence                                                                  #
# --------------------------------------------------------------------------- #
async def generate_and_persist_scenario(
    req: WorksheetRequest, user_id: str
) -> tuple[str, WorksheetResponse, list[str]]:
    worksheet = await generate_worksheet(req)
    lesson_id, exercise_ids = await store.create_lesson(
        user_id=user_id,
        target_language=req.target_language,
        scenario=req.scenario,
        difficulty=req.difficulty,
        worksheet=worksheet.model_dump(),
        mode="scenario",
        grammar_focus=req.grammar_focus,
        exercises=[ex.model_dump() for ex in worksheet.exercises],
    )
    return lesson_id, worksheet, exercise_ids


async def generate_and_persist_verb(
    req: VerbWorksheetRequest, user_id: str
) -> tuple[str, WorksheetResponse, list[str]]:
    worksheet = await generate_verb_worksheet(req)
    scenario = f'Verb practice: "{req.verb}"'
    lesson_id, exercise_ids = await store.create_lesson(
        user_id=user_id,
        target_language=req.target_language,
        scenario=scenario,
        difficulty=req.difficulty,
        worksheet=worksheet.model_dump(),
        mode="verb",
        verb=req.verb,
        grammar_focus=req.grammar_focus,
        exercises=[ex.model_dump() for ex in worksheet.exercises],
    )
    return lesson_id, worksheet, exercise_ids
