"""
main.py
~~~~~~~

FastAPI application exposing REST endpoints for translation, grammar
assessment, and conversation generation for a multi-language language
learning platform. The API acts as an interface between a React front-end
and Azure services such as Translator, Speech, and OpenAI.

Endpoints:
    POST /translate: Translate a piece of text from one language into one or
        more target languages.
    POST /grammar: Evaluate grammar and tense usage of a sentence and
        return feedback.
    POST /chat: Generate a response in an ongoing conversation. Accepts
        chat history to maintain context.

Additional endpoints (speech-to-text / text-to-speech) can be added in
future iterations.
"""

from __future__ import annotations

from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import azure_client

app = FastAPI(title="Language Learning API", description="APIs for translation, grammar checking, and conversation", version="0.1.0")


class TranslateRequest(BaseModel):
    """Request body for the /translate endpoint."""
    text: str
    from_lang: str
    to_langs: List[str]


class GrammarRequest(BaseModel):
    """Request body for the /grammar endpoint."""
    sentence: str
    language: str


class ChatRequest(BaseModel):
    """Request body for the /chat endpoint.

    The history parameter accepts a list of messages, where each message
    contains a role (either 'user' or 'assistant') and the content of
    that message. This allows the model to maintain context across
    turns.
    """
    history: List[Dict[str, str]]
    language: str


@app.post("/translate")
def translate(req: TranslateRequest) -> Any:
    """Translate text into one or more languages.

    :param req: TranslateRequest containing text, source language, and target languages.
    :return: The response from Azure Translator API.
    """
    try:
        result = azure_client.translate_text(req.text, req.from_lang, req.to_langs)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/grammar")
def grammar(req: GrammarRequest) -> Dict[str, str]:
    """Check the grammar of a sentence and provide feedback.

    :param req: GrammarRequest containing the sentence and language.
    :return: A dictionary with a 'feedback' field.
    """
    try:
        feedback = azure_client.grammar_check(req.sentence, req.language)
        return {"feedback": feedback}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/chat")
def chat(req: ChatRequest) -> Dict[str, str]:
    """Generate a conversational response based on history.

    :param req: ChatRequest containing chat history and target language.
    :return: A dictionary with a 'response' field.
    """
    try:
        reply = azure_client.chat_conversation(req.history, req.language)
        return {"response": reply}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/")
def root() -> Dict[str, str]:
    """Simple root endpoint to verify that the service is running."""
    return {"message": "Language Learning API is up and running"}
