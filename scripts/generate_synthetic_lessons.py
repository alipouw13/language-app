"""
Synthetic lesson generator.

Generates scenario → worksheet JSON pairs for:
  - Potential fine-tuning of custom models
  - Evaluation benchmarking
  - Offline testing and development

Outputs a JSONL file with 1,000 synthetic lessons covering:
  - French, Spanish, English
  - CEFR levels A1–C2
  - Diverse grammar topics and real-life scenarios

Usage:
    python scripts/generate_synthetic_lessons.py [--count 1000] [--output data/synthetic_lessons.jsonl]

Requires AZURE_OPENAI_* environment variables in backend/.env
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from app.services.llm_service import chat_completion_json

# -------------------------------------------------------------------
# Scenario templates — combinatorial variety
# -------------------------------------------------------------------

SCENARIOS = [
    "Ordering food at a restaurant",
    "Checking into a hotel",
    "Asking for directions in the city",
    "Shopping at a clothing store",
    "Visiting a doctor's office",
    "Making a phone reservation",
    "Introducing yourself at a party",
    "Negotiating at a flea market",
    "Taking public transportation",
    "Renting an apartment",
    "Opening a bank account",
    "Attending a job interview",
    "Complaining about a product",
    "Planning a weekend trip",
    "Discussing the weather",
    "Describing your daily routine",
    "Talking about hobbies",
    "Explaining a recipe",
    "Discussing a movie you watched",
    "Asking about someone's family",
    "Describing childhood memories",
    "Making plans for the evening",
    "Reporting a lost item to police",
    "Getting a haircut at the salon",
    "Booking a flight at a travel agency",
    "Returning an item at a store",
    "Discussing current events",
    "Applying for a library card",
    "Enrolling in a language class",
    "Describing your hometown",
]

GRAMMAR_TOPICS = {
    "A1": [
        "present tense regular verbs",
        "articles and gender",
        "basic adjective agreement",
        "subject pronouns",
        "common prepositions",
        "numbers and time",
    ],
    "A2": [
        "past tense (passé composé / pretérito)",
        "reflexive verbs",
        "possessive adjectives",
        "comparative adjectives",
        "negation",
        "direct object pronouns",
    ],
    "B1": [
        "imperfect tense",
        "future tense",
        "conditional mood",
        "relative pronouns",
        "indirect object pronouns",
        "adverbs of frequency",
    ],
    "B2": [
        "subjunctive mood (present)",
        "past subjunctive",
        "passive voice",
        "reported speech",
        "compound tenses",
        "idiomatic expressions",
    ],
    "C1": [
        "literary tenses (passé simple / pretérito anterior)",
        "advanced subjunctive uses",
        "nominalization",
        "discourse connectors",
        "register and formality",
        "complex relative clauses",
    ],
    "C2": [
        "stylistic inversion",
        "archaic and literary forms",
        "nuanced modal verbs",
        "complex conditional chains",
        "rhetorical devices",
        "professional and technical register",
    ],
}

LANGUAGES = ["fr", "es", "en"]
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
LANGUAGE_NAMES = {"fr": "French", "es": "Spanish", "en": "English"}

SYSTEM_PROMPT = """\
You are an expert language teacher generating training data for a language learning platform.
Generate a structured worksheet as a SINGLE JSON object with these exact keys:
- scenario_summary (string)
- vocabulary (array of objects with word, translation, example_sentence) — 8-12 items
- grammar_focus (string)
- explanations (string)
- exercises (array of objects with type, question, answer, hint) — 6-10 items
  type must be one of: fill_blank, conjugation, sentence_building, translation
- roleplay_prompts (array of strings) — 3-5 items
Return ONLY valid JSON."""


def _build_prompt(scenario: str, language: str, level: str, grammar: str) -> str:
    lang_name = LANGUAGE_NAMES[language]
    return (
        f"Create a {lang_name} language worksheet.\n"
        f"Scenario: {scenario}\n"
        f"CEFR Level: {level}\n"
        f"Grammar focus: {grammar}\n"
        f"Ensure all vocabulary, examples, and exercises are appropriate for {level} learners."
    )


async def generate_one(scenario: str, language: str, level: str, grammar: str) -> dict | None:
    """Generate a single synthetic lesson. Returns None on failure."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_prompt(scenario, language, level, grammar)},
    ]
    try:
        worksheet = await chat_completion_json(messages, temperature=0.6, max_tokens=4096)
        return {
            "scenario": scenario,
            "language": language,
            "level": level,
            "grammar_focus": grammar,
            "worksheet": worksheet,
        }
    except Exception as e:
        print(f"  [SKIP] {scenario}/{language}/{level}: {e}", file=sys.stderr)
        return None


async def generate_batch(count: int, output_path: str):
    """Generate `count` synthetic lessons and write to JSONL."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Build a deterministic list of combinations, then sample
    combos = []
    for lang in LANGUAGES:
        for level in LEVELS:
            topics = GRAMMAR_TOPICS[level]
            for scenario in SCENARIOS:
                for grammar in topics:
                    combos.append((scenario, lang, level, grammar))

    random.seed(42)
    random.shuffle(combos)
    selected = combos[:count]

    generated = 0
    failed = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for i, (scenario, lang, level, grammar) in enumerate(selected):
            print(f"[{i+1}/{count}] {lang}/{level}: {scenario[:40]}... ({grammar})")
            result = await generate_one(scenario, lang, level, grammar)
            if result:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                generated += 1
            else:
                failed += 1

            # Rate limiting — avoid hitting API throttle
            if (i + 1) % 5 == 0:
                await asyncio.sleep(1)

    print(f"\nDone: {generated} generated, {failed} failed, saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic language learning lessons")
    parser.add_argument("--count", type=int, default=1000, help="Number of lessons to generate")
    parser.add_argument(
        "--output",
        type=str,
        default="data/synthetic_lessons.jsonl",
        help="Output JSONL file path",
    )
    args = parser.parse_args()

    asyncio.run(generate_batch(args.count, args.output))


if __name__ == "__main__":
    main()
