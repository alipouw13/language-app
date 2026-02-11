# Language Learning Application

This project implements a prototype language learning platform that allows
learners to practice French, Spanish and English through both text and
spoken interactions. It combines a React front‑end with a FastAPI back‑end
that integrates Azure services for real‑time translation, grammar
evaluation and conversational practice.

## Key Features

* **Multi‑language voice & text translation** – The back‑end uses Azure
  Translator to translate sentences between languages. The repository
  examples show how translation is achieved with sub‑second latency
  using WebSockets【447753464335382†L270-L284】.
* **FastAPI orchestration** – The API layer is built with FastAPI,
  exposing endpoints for translation, grammar checking and chat. The
  architecture follows the pattern illustrated in the real‑time
  translation sample, where a FastAPI orchestrator buffers incoming
  speech, calls Azure AI services, and broadcasts translated results
  over WebSockets【447753464335382†L331-L340】.
* **Grammar feedback** – Sentences submitted by the learner are
  evaluated by a Large Language Model (LLM) through the OpenAI
  Python SDK. The model provides corrections and explanations for
  incorrect tense usage.
* **Conversational practice** – The chat endpoint maintains a
  conversation history and generates new responses in the target
  language. The model encourages correct verb tenses and provides
  gentle corrections when mistakes occur.
* **Extensible for speech** – Although this prototype focuses on
  translation and grammar, the architecture is designed to be extended
  with Azure Speech services. Azure’s pronunciation assessment can be
  used to give learners feedback on the accuracy and fluency of their
  spoken audio【317289399074311†L47-L49】.

## Repository Structure

```text
language-app/
├── backend/              # FastAPI server and service wrappers
│   ├── main.py           # API definitions
│   ├── azure_client.py   # Helpers for Translator and LLM calls
│   ├── requirements.txt  # Python dependencies
│   └── .env.example      # Sample environment configuration
├── frontend/
│   ├── package.json      # NPM dependencies for the React app
│   └── src/
│       ├── App.js        # Root component
│       └── components/   # Feature‑specific UI components
└── README.md             # This file
```

## Getting Started

### Prerequisites

* Node.js v14+ and npm for the front‑end.
* Python 3.9+ for the back‑end.
* An Azure subscription with Translator and (optionally) Azure OpenAI
  resources. If you wish to use pronunciation assessment, you will
  also need an Azure Speech resource.

### Setup

1. **Clone the repository**:

   ```bash
   git clone <this-repo-url>
   cd language-app
   ```

2. **Configure the back‑end**:

   Copy the `.env.example` file to `.env` and replace the placeholder
   values with your Azure Translator key, endpoint and region. If you
   plan to use grammar and chat features, also set `OPENAI_API_KEY` and
   `OPENAI_API_BASE` (for Azure OpenAI) in the `.env` file.

   ```bash
   cd backend
   cp .env.example .env
   # edit .env with your credentials
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

   This starts the FastAPI server on `http://localhost:8000`.

3. **Configure the front‑end**:

   In a separate terminal, install the front‑end dependencies and run
   the React development server.

   ```bash
   cd ../frontend
   npm install
   npm start
   ```

   Open your browser at `http://localhost:3000` to use the app.

## Usage

* Use the translation form to translate text between English, French
  and Spanish. The API calls Azure Translator, which accepts a
  request body with the input text and returns a JSON response with
  translations【545243807992163†L714-L783】.
* Try the grammar practice section to enter a sentence in your target
  language. The back‑end uses a language model to provide feedback on
  grammar, tense and conjugation.
* In the conversation practice area, chat with the AI in your target
  language. The model maintains context and steers the dialogue toward
  practicing verb tenses.

## Extending the Prototype

This project is intended as a starting point. To add full voice
capabilities:

1. Implement endpoints that accept audio from the client and use
   Azure Speech to transcribe speech to text. Pronunciation assessment
   can then be called to evaluate the accuracy and fluency of the
   learner’s speech【317289399074311†L47-L49】.
2. Implement text‑to‑speech using Azure Speech’s neural voices to
   synthesize translations and AI responses, returning audio streams to
   the client.
3. Introduce WebSocket channels between the React front‑end and
   FastAPI back‑end to support real‑time streaming of audio and
   translations, following the pattern described in the real‑time
   translation reference architecture【447753464335382†L331-L340】.

With these additions, the app can deliver the fully conversational,
Duolingo‑style experience you envision.