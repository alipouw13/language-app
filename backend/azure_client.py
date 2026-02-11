"""
azure_client.py
~~~~~~~~~~~~~~~~~

Utility functions for interacting with Azure services used by the language
learning application. This module wraps calls to the Azure Translator REST
API for text translation and leverages the OpenAI Python SDK to perform
grammar evaluation and conversation generation. Credentials are loaded
from environment variables; see the accompanying `.env` file for names.

Note: These functions assume valid credentials have been provisioned. The
Azure Translator REST API key and endpoint must be provided via
`AZURE_TRANSLATOR_KEY` and `AZURE_TRANSLATOR_ENDPOINT`, respectively.
Optionally, set `AZURE_TRANSLATOR_REGION` if your resource is regional.
OpenAI API access requires `OPENAI_API_KEY` and, for Azure OpenAI,
`OPENAI_API_BASE` to specify the endpoint.

Because this sample runs in an offline environment, you may see
placeholder responses when credentials are missing. In a production
deployment, these functions will raise exceptions if keys are not set.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

try:
    import openai  # type: ignore
except ImportError:
    # In environments without the openai library installed, define a
    # shim so that the module still loads. The grammar_check and
    # chat_conversation functions will return placeholder responses.
    openai = None  # type: ignore

# Load environment variables from a `.env` file if present. This allows
# developers to keep secrets out of source control. When deploying to
# Azure, use secure secret management (e.g. Key Vault) instead.
load_dotenv()

# Translator service configuration
TRANSLATOR_ENDPOINT: str | None = os.getenv("AZURE_TRANSLATOR_ENDPOINT")
TRANSLATOR_KEY: str | None = os.getenv("AZURE_TRANSLATOR_KEY")
TRANSLATOR_REGION: str | None = os.getenv("AZURE_TRANSLATOR_REGION")

# OpenAI (or Azure OpenAI) configuration
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE: str | None = os.getenv("OPENAI_API_BASE")

if openai and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    if OPENAI_API_BASE:
        # When using Azure OpenAI, the base URL must be set to your
        # endpoint (e.g. https://<resource-name>.openai.azure.com/)
        openai.api_base = OPENAI_API_BASE


def translate_text(text: str, from_lang: str, to_langs: List[str]) -> Any:
    """Translate the given text from one language into one or more target
    languages using the Azure Translator REST API.

    :param text: The text to translate.
    :param from_lang: The source language code (e.g. 'en', 'fr', 'es').
    :param to_langs: A list of target language codes.
    :return: Parsed JSON response from the Translator API containing
             translation results.
    :raises ValueError: If the translator credentials are not configured.
    :raises requests.HTTPError: If the HTTP request fails.
    """
    if not TRANSLATOR_ENDPOINT or not TRANSLATOR_KEY:
        raise ValueError(
            "Azure Translator credentials are not set. Set AZURE_TRANSLATOR_ENDPOINT and AZURE_TRANSLATOR_KEY."
        )

    # Construct request URL and parameters
    path = "/translate"
    constructed_url = f"{TRANSLATOR_ENDPOINT}{path}"
    params = {
        "api-version": "3.0",
        "from": from_lang,
        "to": to_langs,
    }

    # Build headers with subscription key and region if provided
    headers: Dict[str, str] = {
        "Ocp-Apim-Subscription-Key": TRANSLATOR_KEY,
        "Content-Type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    if TRANSLATOR_REGION:
        headers["Ocp-Apim-Subscription-Region"] = TRANSLATOR_REGION

    # Single-object request body. You can send multiple objects for batch
    # translation by appending additional dictionaries to this list.
    body = [{"text": text}]

    response = requests.post(constructed_url, params=params, headers=headers, json=body)
    response.raise_for_status()
    return response.json()


def _ensure_openai() -> None:
    """Internal helper to verify that OpenAI SDK is available and
    configured. Raises a ValueError if configuration is incomplete.
    """
    if openai is None:
        raise ValueError(
            "The openai package is not installed. Install it via pip to enable grammar and chat endpoints."
        )
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is not set. Provide your Azure OpenAI or OpenAI API key in the environment."
        )


def grammar_check(sentence: str, language: str) -> str:
    """Evaluate grammar and tense correctness for a sentence in the
    specified language using an LLM. Returns textual feedback with
    suggestions for improvement.

    :param sentence: The sentence to evaluate.
    :param language: The language of the sentence (e.g. 'English', 'French', 'Spanish').
    :return: A feedback string with corrections and explanations.
    """
    try:
        _ensure_openai()
    except ValueError as exc:
        # If OpenAI is unavailable, return a placeholder feedback string
        return f"(Placeholder feedback) Unable to evaluate grammar for: '{sentence}' in {language}. {exc}"

    # Compose a chat prompt instructing the model to act as a grammar tutor
    system_msg = {
        "role": "system",
        "content": f"You are a grammar tutor helping learners improve their {language} sentences."
    }
    user_msg = {
        "role": "user",
        "content": (
            f"Evaluate the following sentence for correct grammar and verb tense usage in {language}. "
            f"If there are mistakes, provide corrections and a brief explanation.\n\nSentence: {sentence}"
        ),
    }
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[system_msg, user_msg],
            temperature=0.3,
        )
        return completion.choices[0].message["content"]
    except Exception as exc:
        # If an API error occurs, return an informative message
        return f"(Error obtaining grammar feedback): {str(exc)}"


def chat_conversation(history: List[Dict[str, str]], language: str) -> str:
    """Generate the next conversational response given a history of
    messages. The assistant will respond in the target language and
    gently correct grammatical mistakes.

    :param history: A list of message dictionaries with 'role' and 'content'.
    :param language: The target language (e.g. 'French', 'Spanish', 'English').
    :return: The assistant's reply.
    """
    try:
        _ensure_openai()
    except ValueError as exc:
        return f"(Placeholder response) Unable to generate conversation reply. {exc}"

    # Prepend a system prompt instructing the assistant on tone and corrections
    system_msg = {
        "role": "system",
        "content": (
            f"You are a friendly conversation partner speaking {language}. "
            f"Engage the learner in a natural dialogue, encourage them to practice verb tenses, "
            f"and gently correct mistakes by providing the correct phrasing when necessary."
        ),
    }
    msgs = [system_msg] + history
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=msgs,
            temperature=0.4,
        )
        return completion.choices[0].message["content"]
    except Exception as exc:
        return f"(Error obtaining conversation reply): {str(exc)}"
