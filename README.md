# Language Learning App

AI-powered language learning platform that showcases **Azure AI Foundry** models
(chat, translation and speech) with all data stored in **Microsoft Fabric OneLake**.
Supports **French**, **Spanish** and **English**.

Generate scenario worksheets, drill individual verbs, translate text, and practice
real conversations by voice or text. Everything is secured with **Microsoft Entra ID**.

## Features

- **Scenario worksheets** — vocabulary, grammar notes and auto-graded exercises for any
  real-life situation, optionally focused on a specific tense.
- **Verb practice** — pick a verb (or type your own) and get a worksheet centred on its
  conjugations, two-way translations, and use in real sentences and conversations.
- **Translate** — powered by a dedicated Azure AI Foundry translation deployment
  (falls back to the chat model when none is configured).
- **Conversation practice** — chat with an AI tutor by text or microphone; speech is
  transcribed with a Foundry speech-to-text model and replies can be spoken back.
- **History** — every worksheet and conversation is persisted to OneLake and browsable
  per user.

## Architecture

| Layer | Technology |
|-------|------------|
| Frontend | React + Vite + TypeScript, MSAL (Entra ID) |
| Backend | FastAPI (async), Entra JWT validation |
| Data | **Microsoft Fabric OneLake Lakehouse** — Delta tables via `deltalake` |
| AI | Azure AI Foundry: chat (`gpt-4.1-mini`), translation, STT (`gpt-4o-transcribe`), TTS (`gpt-4o-mini-tts`) |
| Auth | Microsoft Entra ID end-to-end (`DefaultAzureCredential` for services, bearer tokens for the API) |

The data layer is **config-driven**: the same Delta-table code writes to a local
directory in development (`STORAGE_BACKEND=local`) or to a Fabric Lakehouse over
`abfss` in production (`STORAGE_BACKEND=onelake`), authenticated with Entra ID.

## Prerequisites

- **Node.js** 18+ and **Python** 3.11+
- **Azure CLI** (`az login`) — Entra auth for all Azure services
- An **Azure OpenAI** / **AI Foundry** resource with the deployments below
- (Production) A **Fabric workspace + Lakehouse**, and Entra **app registrations**

## Model deployments

Deploy these in Azure AI Foundry / Azure OpenAI and put the deployment names in `.env`:

| Purpose | Recommended model | Setting |
|---------|-------------------|---------|
| Chat + evaluation + worksheets | `gpt-4.1-mini` (or `gpt-4o-mini`) | `AZURE_OPENAI_DEPLOYMENT` |
| Speech-to-text | `gpt-4o-transcribe` (or `gpt-4o-mini-transcribe`) | `AZURE_SPEECH_TO_TEXT_MODEL_NAME` |
| Text-to-speech | `gpt-4o-mini-tts` | `AZURE_TEXT_TO_SPEECH_MODEL_NAME` |
| Translation (optional, dedicated) | a chat model such as `gpt-4o-mini` | `AZURE_TRANSLATION_MODEL_NAME` |

> **Note:** the previous build pointed STT at `gpt-4o-transcribe-diarize`, which is not a
> standard transcription deployment — switch it to `gpt-4o-transcribe`. If you don't have a
> separate translation deployment, leave `AZURE_TRANSLATION_MODEL_NAME` empty and the chat
> model is used.

## Quick start

### 1. Backend

> **Windows on ARM (important):** create the venv with an **x64 Python 3.11**, not the
> ARM64 build. `deltalake` (and some other native wheels) ship prebuilt **win_amd64**
> wheels but **not win_arm64**, so an ARM64 interpreter tries to compile from source and
> fails. Use the launcher to pick the x64 3.11 explicitly: `py -3.11`. Check your venv with
> `python -c "import platform; print(platform.machine())"` → it should print `AMD64`.

```bash
cd backend
py -3.11 -m venv venv            # Windows: x64 Python 3.11 (or: python3.11 -m venv venv)
venv\Scripts\activate            # Windows (or: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # edit with your endpoints
az login                         # Entra auth for Azure services
uvicorn app.main:app --reload --port 8000
```

By default `STORAGE_BACKEND=local` writes Delta tables under `backend/.lakehouse/`,
and `ENTRA_AUTH_ENABLED=false` bypasses sign-in — so the app runs immediately.
API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env           # optional; defaults work for local dev
npm run dev
```

Open http://localhost:5173

## Two layers of authentication

It's worth being precise about what "Entra auth for everything" means here, because
there are **two independent layers**:

1. **Service → Azure (always on).** The backend authenticates to Azure OpenAI, Foundry
   and OneLake with Microsoft Entra via `DefaultAzureCredential` — your `az login`
   locally, or a managed identity when hosted. **No API keys, no app registration.**
   This alone is enough to run the whole app.
2. **User → API (optional).** Making *browser users* sign in to the API (so data is
   per-user and the endpoints aren't open). This is the only part that needs an app
   registration, and it's **off by default** — you don't need it for your own use,
   because a `cognitiveservices.azure.com` token from `az login` is not valid for your
   own API. Enable it only when hosting for multiple users (see below).

## Enabling user sign-in (Microsoft Entra ID)

The app is fully wired for layer 2 and runs unauthenticated only when the flags below are off.

**Backend** (`backend/.env`):

```env
ENTRA_AUTH_ENABLED=true
ENTRA_TENANT_ID=<tenant-id>
ENTRA_API_AUDIENCE=api://<api-client-id>
```

**Frontend** (`frontend/.env`):

```env
VITE_AUTH_ENABLED=true
VITE_ENTRA_CLIENT_ID=<spa-app-client-id>
VITE_ENTRA_TENANT_ID=<tenant-id>
VITE_ENTRA_API_SCOPE=api://<api-client-id>/access_as_user
```

Register two Entra applications: an **API** app (exposes the `access_as_user` scope) and a
**SPA** app (redirect URI `http://localhost:5173`, with delegated permission to the API
scope). The backend validates the bearer token's signature, issuer and audience against the
tenant JWKS; the WebSocket accepts the token as a `?token=` query parameter.

## Targeting Fabric OneLake

```env
STORAGE_BACKEND=onelake
ONELAKE_WORKSPACE=<workspace-name-or-guid>
ONELAKE_LAKEHOUSE=<lakehouse-name-or-guid>
```

The signed-in identity (via `DefaultAzureCredential`) needs **Contributor** on the Fabric
workspace. Tables are created lazily as Delta tables under the Lakehouse `Tables/` area:
`users`, `lessons`, `exercises`, `exercise_scores`, `conversations`, `conversation_turns`.

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/worksheets` | Generate a scenario worksheet |
| `POST` | `/api/worksheets/verb` | Generate a verb-focused worksheet |
| `GET`  | `/api/worksheets/verbs` | Curated verb list for the picker |
| `POST` | `/api/worksheets/evaluate` | Score an exercise answer |
| `POST` | `/api/translate` | Translate text (Foundry translation model) |
| `POST` | `/api/conversations` | Start a conversation |
| `POST` | `/api/conversations/{id}/message` | Send a message |
| `WS`   | `/api/conversations/{id}/ws` | Voice/text streaming |
| `POST` | `/api/speech/transcribe` | Speech-to-text |
| `GET`  | `/api/lessons` | List saved worksheets |
| `GET`  | `/api/lessons/conversations` | List conversations |

## Project structure

```
backend/app/
├── api/           # Route handlers (Entra-protected)
├── auth/          # Entra ID JWT validation
├── services/      # LLM, translation, speech, worksheet, conversation logic
├── repository/    # Fabric OneLake Lakehouse (Delta) data layer
├── models/        # Pydantic schemas
└── config.py
frontend/src/
├── pages/         # Scenario, Verb practice, Conversation, Translate, History
├── components/    # Layout + reusable UI + worksheet renderer
├── auth/          # MSAL config, provider, token acquisition
├── services/      # API + WebSocket clients
└── state/
```

## License

Educational purposes.
