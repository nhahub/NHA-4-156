# Astrolabe

An AI-powered codebase explorer that ingests a GitHub repository — public or private — and provides semantic search, interactive chat, automated insights, visual analytics, and auto-generated documentation, all through a space-themed React frontend.

> Internally the project is still named `repo-illustrator` (DB filename, Docker service). Only the user-facing name changed.

## Features

- **Ingest any GitHub repo** — clones, chunks by language (tree-sitter), embeds with `nomic-embed-text-v1.5`, stores in ChromaDB. Skips re-embedding if nothing changed.
- **Sign in with GitHub** — OAuth login. Private repos are cloned with the signed-in user's own token, and access is re-checked against GitHub before anyone can read a private repo's chat, charts, insights, or docs.
- **Chat with your codebase** — a ReAct agent powered by Groq, OpenRouter, or Anthropic that can semantically search the vector store, read files, grep, and explore the directory tree. Streaming responses with thinking visibility.
- **Repo insights** — an LLM agent explores the repo and returns a structured summary: purpose, tech stack, architecture, key files.
- **Charts & analytics** — language breakdown pie chart, dependency graph by ecosystem, contributor histogram with commit/additions/deletions, health score (stars/recency/issues/CI/tests/contributors/docs), codebase analytics (LOC, TODOs, complex/hot files, test coverage estimate).
- **Auto-generated documentation** — function/class summaries and API endpoint explorer, extracted by an LLM agent reading the source.
- **Session management** — persistent chat history per repo and per user, stored in SQLite.

## Architecture

```
Frontend (React 19 + Vite + Tailwind CSS 4)
       │
       │ HTTP / SSE  (+ signed session cookie)
       ▼
FastAPI Backend (Uvicorn)
       │
       ├── SessionMiddleware (signed cookie) + GitHub OAuth
       ├── ChromaDB (vector store, on-disk)
       ├── SQLite (users, registry, access grants, sessions, insights, charts, docs)
       ├── Embeddings (HuggingFace, local CPU/GPU)
       ├── Reranker (CrossEncoder, local CPU)
       ├── GitHub API (repo probe, contributor stats)
       └── LLM APIs (Groq / OpenRouter / Anthropic — cloud only)
```

All ML models run locally (embedding + reranking). LLM inference is 100% cloud API calls — no GPU required for serving.

## Authentication & access control

Login is a standard **GitHub OAuth App** flow (scopes: `read:user repo`). The browser is redirected to GitHub, comes back to `/auth/callback`, and the backend sets a **signed session cookie** containing only the user id.

The user's GitHub token is **Fernet-encrypted at rest** in SQLite (`api/security.py`) and is **never sent to the browser** — `/auth/me` returns profile fields only. It's decrypted on demand server-side, because it has to be spent on `git clone` and GitHub API calls.

Authorization (`api/auth.py`):

- **Public repos** — readable by anyone, logged in or not.
- **Private repos** — require a login. On first access the backend probes GitHub with *that user's* token to confirm they're a collaborator, then caches the grant in a `repo_access` row so subsequent checks are a local DB hit.
- **Chat sessions** — scoped to their owner; another user's session id returns `404`, not `403`, so session existence isn't leaked.

Private repos are cloned using the signed-in user's token, so the app can only ever see what that user can already see.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| Vector DB | ChromaDB |
| Database | SQLite |
| LLM integration | LlamaIndex (ReActAgent) |
| LLM providers | Groq, OpenRouter, Anthropic |
| Embeddings | `nomic-embed-text-v1.5` via sentence-transformers |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Code parsing | tree-sitter (Python, JS/TS, Java, C++, C#, Go, Rust, Ruby) |
| Frontend | React 19, Vite, Tailwind CSS 4, Framer Motion |
| Routing | react-router-dom |

## Prerequisites

- Python 3.10+
- Node.js 20+
- API keys for at least one LLM provider (Groq, OpenRouter, or Anthropic)
- Git (for cloning repos)
- A [GitHub OAuth App](https://github.com/settings/developers) (for login and private repos)

### Registering the OAuth App

Create an OAuth App and set its **Authorization callback URL** to exactly the URL the browser lands on:

| Environment | Callback URL |
|---|---|
| Docker / production (single port) | `https://your-domain/auth/callback` |
| Local Vite dev | `http://localhost:5173/auth/callback` |

GitHub requires a byte-for-byte match, so local dev and production generally need **two separate OAuth Apps**. Copy the client ID and secret into `.env`.

## Quick Start

### Option A — Docker (recommended)

```bash
cp .env.example .env   # edit with your API keys
docker compose up --build
```

The frontend and backend are served on `http://localhost:8000`. The first build downloads ML models (~500MB) into the image.

### Option B — Local dev (backend + frontend separately)

#### 1. Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your API keys
uvicorn api.main:app
```

API at `http://localhost:8000`, docs at `http://localhost:8000/docs`.

#### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend at `http://localhost:5173`, expects the backend at `http://localhost:8000`. Set `VITE_API_BASE_URL` in `frontend/.env` to change the backend URL.

## Environment Variables

### LLM providers

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes\* | — | Groq API key |
| `OPENROUTER_API_KEY` | Yes\* | — | OpenRouter API key |
| `ANTHROPIC_API_KEY` | Yes\* | — | Anthropic API key |
| `GROQ_MODEL` | No | `llama3-70b-8192` | Default Groq model |
| `OPENROUTER_MODEL` | No | `anthropic/claude-haiku-4.5` | Default OpenRouter model |
| `ANTHROPIC_MODEL` | No | `claude-haiku-4-5-20251001` | Default Anthropic model |

\*At least one LLM provider key is required.

### Auth

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_OAUTH_CLIENT_ID` | Yes | — | OAuth App client ID |
| `GITHUB_OAUTH_CLIENT_SECRET` | Yes | — | OAuth App client secret |
| `SESSION_SECRET_KEY` | **Yes in prod** | insecure dev default | Signing key for the session cookie. Any long random string. **If unset the app boots with a hardcoded, repo-committed default and anyone can forge a session cookie for any user.** |
| `FERNET_KEY` | Yes | — | Symmetric key encrypting GitHub tokens at rest. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Rotating it invalidates every stored token (users just log in again). |
| `SESSION_COOKIE_SECURE` | No | `0` | Set to `1` in production to mark the cookie HTTPS-only. |
| `SESSION_COOKIE_MAX_AGE` | No | `0` (browser session) | Cookie lifetime in seconds. `2592000` gives a 30-day "remember me". |

### Deployment

| Variable | Required | Default | Description |
|---|---|---|---|
| `FRONTEND_ORIGIN` | Local dev only | — | Where to send the browser after login. Set to `http://localhost:5173` for Vite dev. **Leave unset in Docker/production** — the app then builds the callback from the incoming request, which is correct for the single-port deployment. |
| `CORS_ALLOW_ORIGINS` | No | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed origins. Cannot be `*`, because the frontend sends credentials. |
| `GITHUB_TOKEN` | No | — | Fallback server-side token, used only for anonymous GitHub API calls (contributor stats rate limit: 60 → 5000 req/hr). Private repos are cloned with the signed-in **user's** token, not this one. |

> **Note:** `.env.example` currently ships the LLM and auth keys but not `FRONTEND_ORIGIN`, `CORS_ALLOW_ORIGINS`, or `SESSION_COOKIE_MAX_AGE`. They're read at import time in `api/main.py` and `api/auth.py`, so they work — they're just undocumented there.

## API Endpoints

Auth routes sit at the root. Everything else is prefixed with `/repos`.

### Auth

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/login` | Redirect to GitHub. `?next=/path` returns the user to the page they started from. |
| `GET` | `/auth/callback` | OAuth callback: validates `state`, exchanges the code, sets the session cookie |
| `POST` | `/auth/logout` | Clear the session (the encrypted token stays in the DB for next login) |
| `GET` | `/auth/me` | Logged-in user's public profile, or `401` |

### Ingestion

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingest` | Ingest a repo by URL (runs in background) |
| `POST` | `/{repo_id}/stop` | Cancel an in-flight ingestion |
| `GET` | `/{repo_id}/status` | Check ingestion status |
| `GET` | `/` | List all ingested repos |
| `DELETE` | `/{repo_id}` | Delete repo (ChromaDB, disk, DB, caches) |

### Chat — all require a login

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat/{repo_id}` | Send a message (sync response) |
| `POST` | `/chat/{repo_id}/stream` | Send a message (SSE streaming response) |
| `GET` | `/chat/{repo_id}/sessions` | List your sessions for this repo |
| `GET` | `/chat/{session_id}/history` | Get chat history |
| `DELETE` | `/chat/{session_id}` | Delete a chat session |

### Insights

| Method | Path | Description |
|---|---|---|
| `POST` | `/{repo_id}/insight` | Start insight generation (background) |
| `GET` | `/{repo_id}/insight` | Get insight result (purpose, tech stack, architecture, key files) |

### Charts

| Method | Path | Description |
|---|---|---|
| `POST` | `/{repo_id}/charts` | Start chart data generation (background) |
| `GET` | `/{repo_id}/charts` | Get chart data (language pie, dependencies, contributors, analytics) |

### Documentation

| Method | Path | Description |
|---|---|---|
| `POST` | `/{repo_id}/docs` | Start docs generation (background) |
| `GET` | `/{repo_id}/docs` | Get generated docs (function summaries + API endpoints) |

All `/repos` endpoints for a **private** repo require a session cookie and an access check; chat endpoints require a login unconditionally. Full request/response schemas are in the interactive docs at `/docs` or in [`docs/api.md`](docs/api.md).

Known bugs, cost problems, and planned performance work are tracked in [`docs/IMPROVEMENTS.md`](docs/IMPROVEMENTS.md).

## Project Structure

```
.
├── api/                    # FastAPI application
│   ├── main.py             # App entry, lifespan, sessions, CORS, router registration
│   ├── auth.py             # OAuth flow, User model, access-control dependencies
│   ├── security.py         # Fernet encrypt/decrypt for GitHub tokens at rest
│   ├── database.py         # SQLite schema and CRUD
│   └── routes/
│       ├── auth.py         # GET /auth/login, /auth/callback, /auth/me, POST /auth/logout
│       ├── ingestion.py    # POST /ingest, GET/DELETE /{repo_id}
│       ├── chat.py         # POST /chat/{repo_id}, /stream, history, delete
│       ├── insight.py      # POST/GET /{repo_id}/insight
│       ├── charts.py       # POST/GET /{repo_id}/charts
│       └── docs.py         # POST/GET /{repo_id}/docs
├── embeddings/
│   └── embedder.py         # HuggingFace embedding model (GPU-aware)
├── ingestion/
│   ├── pipeline.py         # Ingestion orchestrator
│   ├── preprocessor.py     # Git clone, file filtering, hash-based change detection
│   ├── loader.py           # File loading
│   └── chunker.py          # Language-aware code chunking
├── vectorstore/
│   └── chroma_store.py     # ChromaDB persistent client
├── llm/
│   └── chatbot.py          # ReActAgent with streaming, memory, tool use
├── rag/
│   ├── engine.py           # Vector store index loader
│   ├── agent_tools.py      # LLM provider factory + file exploration tools
│   ├── reranker.py         # CrossEncoder reranker
│   └── insight_generator.py# Insight generation agent
├── insights/
│   ├── provider.py         # Chart data extraction (LLM + GitHub API)
│   ├── visualizer.py       # Chart-ready JSON transformation
│   ├── analyzer.py         # Static analysis, health score, GitHub stats
│   └── document_generator.py # Auto-documentation agent
├── frontend/               # React SPA
│   └── src/
│       ├── App.jsx         # Landing page (ingest URL / assistant mode)
│       ├── pages/
│       │   └── RepoIllustrationPage.jsx  # Dashboard: charts, docs, chat
│       ├── components/
│       │   ├── ChatWindow.jsx     # Streaming chat with thinking toggle
│       │   ├── AuthButton.jsx     # Sign in with GitHub / avatar dropdown
│       │   ├── Navbar.jsx
│       │   ├── Starfield.jsx
│       │   ├── FloatingWords.jsx
│       │   ├── SearchBar.jsx
│       │   └── ModeToggle.jsx
│       └── lib/
│           ├── api.jsx           # API client (all endpoints)
│           ├── auth.jsx          # AuthProvider / useAuth — session state, login, logout
│           └── session.jsx       # Chat session ID persistence
├── static/                 # built React app (Docker only, gitignored)
├── data/                   # (gitignored) cloned & processed repos
├── chroma_db/              # (gitignored) vector index
├── repo_illustrator.db     # (gitignored) SQLite DB
├── Dockerfile              # multi-stage build (frontend + backend)
├── docker-compose.yml      # single service with persisted volumes
├── .Dockerignore
├── requirements.txt
├── .env.example
└── docs/
    ├── api.md              # API documentation
    └── IMPROVEMENTS.md     # Known bugs, cost & performance backlog
```

## Docker

### Build & Run

```bash
docker compose up --build
```

The container serves everything on port `8000` — the built React frontend is served as static files by the FastAPI backend, so there's only one port to expose.

### Multi-stage build

The `Dockerfile` does two things at build time:
1. **Stage 1** — builds the React app with `node:20-alpine`
2. **Stage 2** — installs Python deps, pre-downloads the embedding and reranker models into the image (so the container starts fast), copies backend + built frontend

### Persisted volumes

```yaml
volumes:
  - ./data:/app/data              # cloned & processed repos
  - ./chroma_db:/app/chroma_db    # vector embeddings
  - ./repo_illustrator.db:/app/repo_illustrator.db  # SQLite DB
```

Without these volumes, every `docker compose down` wipes all ingested repos and embeddings.

### Important: first build is slow

The sentence-transformers models (`nomic-embed-text-v1.5` + `cross-encoder/ms-marco-MiniLM-L-6-v2`) are downloaded during `docker build`, which adds ~500MB to the image. Subsequent builds use Docker's layer cache unless `requirements.txt` or the model versions change.

## Troubleshooting

### Charts/docs spin forever and no LLM calls appear in your provider dashboard

The job isn't running — it's a stale `processing` row, not a rate limit. Jobs are `BackgroundTasks` living in process memory, so if the process dies mid-job (redeploy, OOM, crash) the job vanishes but the DB row stays `processing` forever. Nothing resets it, and `POST /{repo_id}/docs` treats a `processing` row as "already running", so it returns `200 OK` and dispatches nothing, forever.

Clear the row (the DB is bind-mounted, no restart needed):

```bash
sqlite3 repo_illustrator.db "DELETE FROM docs WHERE repo_id='<repo_id>';"
# same for the charts / insights tables
```

Tracked as item #1 in [`docs/IMPROVEMENTS.md`](docs/IMPROVEMENTS.md).

### `[WARNING] SESSION_SECRET_KEY not set`

The app is running with a hardcoded, repo-committed signing key, which means **anyone can forge a session cookie for any user**. Set `SESSION_SECRET_KEY` in `.env`.

If you've set it and still see this warning, check that `load_dotenv()` runs at **module import** in `api/main.py`, not inside `lifespan()` — the session secret, CORS origins, and cookie flags are all read at import time, long before `lifespan()` runs. (In Docker this is masked, because `env_file:` injects real environment variables.)

### `TypeError: argument 'source': 'bytes' object is not an instance of 'str'` (CodeSplitter / tree-sitter version conflict)

LlamaIndex's `CodeSplitter` has a known incompatibility with certain versions of `tree-sitter` related to a `bytes`/`str` API change introduced in `0.21+`. If you encounter this error, pin `tree-sitter==0.20.4` with individual language packages. If that fails, check the installed version of `llama-index-core` and match the tree-sitter version it expects.

### Embedding is slow on CPU

The embedding model (`nomic-embed-text-v1.5`) detects GPU automatically. On CPU-only machines (e.g. Oracle Free Tier), ingestion takes longer but works. This is a one-time cost per repo — subsequent reads use the cached index.

### Chat response is slow

The ReAct agent uses tool calls and multiple LLM rounds. For faster responses, use streaming (`POST /chat/{repo_id}/stream`) which shows thinking in real time.

## License

MIT
