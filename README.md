# Language Learning Application

A production-grade, full-stack language learning platform with AI-powered worksheets, voice conversation practice, and persisted lesson history. Supports **French**, **Spanish**, and **English**.

## Architecture

```text
+-----------------+       +--------------------+       +---------------------+
|   React + Vite  | <---> |    FastAPI (async)  | <---> |  Azure OpenAI (LLM) |
|   TypeScript    |       |    PostgreSQL       |       |  Azure Speech (STT) |
|   port 5173     |       |    port 8000        |       |  Azure Speech (TTS) |
+-----------------+       +--------------------+       +---------------------+
```

## Features

### Page 1 — Scenario Worksheet Generator
Enter a real-life scenario, target language, difficulty (A1–C2), and optional grammar focus. The LLM generates a structured worksheet with vocabulary, grammar explanations, exercises, and roleplay prompts. Answers are evaluated by the LLM and persisted.

### Page 2 — Voice Conversation Practice
Start a conversation session with an AI tutor in your target language. Supports text input, with microphone recording wired for future WebSocket streaming via Azure Speech Services. The AI maintains 10-turn context memory and provides inline corrections.

### Page 3 — Past Lessons Library
Browse saved worksheets and conversation transcripts with pagination. View full worksheet details, exercise answers, and conversation replays with correction history.

## Repository Structure

```text
language-app/
├── .gitignore
├── README.md
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point, CORS, routers
│   │   ├── config.py                  # pydantic-settings configuration
│   │   ├── api/
│   │   │   ├── worksheets.py          # Worksheet generation & evaluation
│   │   │   ├── conversations.py       # Conversation CRUD + WebSocket
│   │   │   └── lessons.py             # Paginated lesson/conversation lists
│   │   ├── services/
│   │   │   ├── llm_service.py         # Centralized Azure OpenAI client
│   │   │   ├── worksheet_generator.py # LLM prompt → structured worksheet
│   │   │   ├── evaluation_service.py  # Exercise answer scoring
│   │   │   ├── speech_service.py      # Azure Speech STT/TTS wrappers
│   │   │   └── conversation_service.py# Multi-turn conversation logic
│   │   ├── models/
│   │   │   ├── db_models.py           # SQLAlchemy ORM (6 tables)
│   │   │   └── pydantic_models.py     # Request/response schemas
│   │   └── db/
│   │       ├── session.py             # Async session factory
│   │       └── migrate.py             # Table creation script
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                     # Router + navigation
│       ├── index.css
│       ├── pages/
│       │   ├── ScenarioPage.tsx        # Worksheet generator UI
│       │   ├── ConversationPage.tsx    # Chat + voice UI
│       │   └── LessonsPage.tsx         # Library with pagination
│       ├── services/
│       │   ├── api.ts                  # Axios API client
│       │   └── websocket.ts           # WebSocket client for voice
│       ├── state/
│       │   └── useConversationStore.ts # Conversation state hook
│       └── types/
│           └── index.ts               # Shared TypeScript types
└── scripts/
    └── generate_synthetic_lessons.py   # 1,000 synthetic lesson generator
```

## Database Schema

Six tables with proper relational modeling:

| Table | Purpose |
|---|---|
| `users` | Registered learners |
| `lessons` | Generated worksheets (JSON + metadata) |
| `exercises` | Individual exercises within lessons |
| `exercise_attempts` | User answers with LLM evaluation scores |
| `conversations` | Voice/text conversation sessions |
| `conversation_turns` | Individual turns with corrections |

## Prerequisites

- **Node.js** v18+
- **Python** 3.11+
- **Azure Database for PostgreSQL** Flexible Server (or local PostgreSQL 14+ for development)
- **Azure OpenAI** resource with a GPT-4 deployment
- **Azure Speech Services** with Entra authentication (for voice features)

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/alipouw13/language-app.git
cd language-app

# Set up backend environment
cd backend
cp .env.example .env
# Edit .env with your Azure credentials
```

### 2. Database Setup (Azure PostgreSQL)

The application uses **Azure Database for PostgreSQL Flexible Server** with **Entra authentication**.

| Property | Value |
|----------|-------|
| **Server** | `language-app-pgsql.postgres.database.azure.com` |
| **Database** | `language_app` |
| **Port** | `5432` |
| **Authentication** | Entra (Azure AD) |
| **Region** | North Europe |

The database uses Entra authentication via `DefaultAzureCredential`. Ensure you're logged in with `az login` and have database access granted to your identity.

```
DATABASE_URL=postgresql+asyncpg://<entra-user>:placeholder@language-app-pgsql.postgres.database.azure.com:5432/language_app
```

> **Note:** For local development with a local PostgreSQL instance, you can use password authentication.

### 3. Start Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Tables are auto-created on startup. API docs at `http://localhost:8000/docs`.

### 4. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to the backend.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/api/worksheets` | Generate & persist a worksheet |
| `POST` | `/api/worksheets/preview` | Generate without saving |
| `GET` | `/api/worksheets/{id}` | Get saved lesson detail |
| `POST` | `/api/worksheets/evaluate` | Score an exercise answer |
| `POST` | `/api/conversations` | Start conversation session |
| `POST` | `/api/conversations/{id}/message` | Send text message |
| `GET` | `/api/conversations/{id}` | Get full transcript |
| `WS` | `/api/conversations/{id}/ws` | Voice streaming WebSocket |
| `GET` | `/api/lessons` | Paginated worksheet list |
| `GET` | `/api/lessons/conversations` | Paginated conversation list |

## Synthetic Data Generation

Generate 1,000 synthetic scenario/worksheet pairs for benchmarking or fine-tuning:

```bash
cd scripts
python generate_synthetic_lessons.py --count 1000 --output ../data/synthetic_lessons.jsonl
```

Covers all CEFR levels (A1–C2), three languages, and 30+ real-life scenarios with diverse grammar topics.

## Design Decisions

- **Async throughout**: FastAPI with async SQLAlchemy + asyncpg for non-blocking DB and LLM calls
- **JSON mode for worksheets**: Forces structured output from Azure OpenAI, validated by Pydantic
- **Service layer pattern**: All LLM calls centralized in `services/` — no business logic in routes or components
- **Conversation memory windowing**: Last 10 turns sent to LLM to balance context vs. token cost
- **WebSocket for voice**: Real-time audio streaming with fallback to text-only mode
- **Vite + TypeScript**: Fast HMR, type-safe frontend, proxy to backend removes CORS issues in dev

## Security

- All secrets in `.env` (git-ignored)
- `.env.example` contains only placeholder values
- CORS restricted to dev origins (configure for production)
- For production: use Azure Key Vault + Managed Identity

## License

Educational purposes.
