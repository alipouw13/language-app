"""
Curated common-verb lists per language for the Verb Practice feature.

Each entry pairs the target-language infinitive with its English gloss so the
UI can present a friendly picker. These are starting points — learners may
also type any verb of their own.
"""

from __future__ import annotations

VERBS: dict[str, list[dict[str, str]]] = {
    "fr": [
        {"verb": "être", "gloss": "to be"},
        {"verb": "avoir", "gloss": "to have"},
        {"verb": "aller", "gloss": "to go"},
        {"verb": "faire", "gloss": "to do / make"},
        {"verb": "dire", "gloss": "to say"},
        {"verb": "pouvoir", "gloss": "to be able to"},
        {"verb": "vouloir", "gloss": "to want"},
        {"verb": "venir", "gloss": "to come"},
        {"verb": "prendre", "gloss": "to take"},
        {"verb": "parler", "gloss": "to speak"},
        {"verb": "manger", "gloss": "to eat"},
        {"verb": "boire", "gloss": "to drink"},
        {"verb": "savoir", "gloss": "to know"},
        {"verb": "voir", "gloss": "to see"},
        {"verb": "devoir", "gloss": "to have to / must"},
    ],
    "es": [
        {"verb": "ser", "gloss": "to be (permanent)"},
        {"verb": "estar", "gloss": "to be (state)"},
        {"verb": "tener", "gloss": "to have"},
        {"verb": "hacer", "gloss": "to do / make"},
        {"verb": "ir", "gloss": "to go"},
        {"verb": "poder", "gloss": "to be able to"},
        {"verb": "querer", "gloss": "to want"},
        {"verb": "decir", "gloss": "to say"},
        {"verb": "venir", "gloss": "to come"},
        {"verb": "hablar", "gloss": "to speak"},
        {"verb": "comer", "gloss": "to eat"},
        {"verb": "beber", "gloss": "to drink"},
        {"verb": "saber", "gloss": "to know"},
        {"verb": "ver", "gloss": "to see"},
        {"verb": "dar", "gloss": "to give"},
    ],
    "en": [
        {"verb": "to be", "gloss": "ser / estar"},
        {"verb": "to have", "gloss": "avoir / tener"},
        {"verb": "to go", "gloss": "aller / ir"},
        {"verb": "to do", "gloss": "faire / hacer"},
        {"verb": "to say", "gloss": "dire / decir"},
        {"verb": "to get", "gloss": "obtenir / conseguir"},
        {"verb": "to make", "gloss": "faire / hacer"},
        {"verb": "to know", "gloss": "savoir / saber"},
        {"verb": "to take", "gloss": "prendre / tomar"},
        {"verb": "to come", "gloss": "venir / venir"},
        {"verb": "to want", "gloss": "vouloir / querer"},
        {"verb": "to eat", "gloss": "manger / comer"},
        {"verb": "to drink", "gloss": "boire / beber"},
        {"verb": "to speak", "gloss": "parler / hablar"},
        {"verb": "to see", "gloss": "voir / ver"},
    ],
}


def list_verbs(language: str) -> list[dict[str, str]]:
    return VERBS.get(language, [])
