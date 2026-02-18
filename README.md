# Language Learning App

AI-powered language learning platform with worksheet generation, voice conversation practice, and lesson history. Supports **French**, **Spanish**, and **English**.

![Worksheets](frontend/docs/worksheets.png)

## Features

### Worksheet Generator

Generate structured worksheets for real-life scenarios with vocabulary, grammar explanations, exercises, and roleplay prompts. LLM evaluates your answers.

<details>
<summary>View screenshots</summary>

![Worksheet Example 1](frontend/docs/worksheet-1.png)
![Worksheet Example 2](frontend/docs/worksheet-2.png)
![Worksheet Example 3](frontend/docs/worksheet-3.png)

</details>

### Conversation Practice

Chat with an AI tutor in your target language. The AI maintains context and provides inline corrections.

![Conversation](frontend/docs/convos.png)

<details>
<summary>View example conversation</summary>

![Conversation Example](frontend/docs/convo-example.png)

</details>

### Past Lessons

Browse saved worksheets and conversation transcripts with pagination.

![Past Lessons](frontend/docs/past-lessons.png)

## Tech Stack

| Frontend | Backend | Services |
|----------|---------|----------|
| React + Vite | FastAPI (async) | Azure OpenAI (GPT-4) |
| TypeScript | PostgreSQL + SQLAlchemy | Azure Speech (STT/TTS) |
| Port 5173 | Port 8000 | Entra Authentication |

## Prerequisites

- **Node.js** 18+ and **Python** 3.11+
- **PostgreSQL** (Azure or local)
- **Azure OpenAI** with GPT-4 deployment

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/alipouw13/language-app.git
cd language-app/backend
cp .env.example .env   # Edit with your Azure credentials
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows (or: source venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Tables auto-create on startup. API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Environment Variables

Create `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/language_app
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4
```

For Azure PostgreSQL with Entra auth, use `az login` and configure your identity.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/worksheets` | Generate worksheet |
| `POST` | `/api/worksheets/evaluate` | Score answer |
| `POST` | `/api/conversations` | Start conversation |
| `POST` | `/api/conversations/{id}/message` | Send message |
| `GET` | `/api/lessons` | List worksheets |
| `GET` | `/api/lessons/conversations` | List conversations |

## Project Structure

```
backend/
├── app/
│   ├── api/           # Route handlers
│   ├── services/      # LLM, speech, evaluation logic
│   ├── models/        # SQLAlchemy + Pydantic models
│   └── db/            # Database session & migrations
frontend/
├── src/
│   ├── pages/         # React page components
│   ├── services/      # API & WebSocket clients
│   └── state/         # State management
```

## Database

Six tables: `users`, `lessons`, `exercises`, `exercise_attempts`, `conversations`, `conversation_turns`

## License

Educational purposes.
