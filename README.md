# Repo-Illustrator

An AI-powered codebase explorer that ingests any public GitHub repository and provides semantic search, interactive chat, automated insights, visual analytics, and auto-generated documentation — all through a space-themed React frontend.

## Features

- **Ingest any public GitHub repo** — clones, chunks by language (tree-sitter), embeds with `nomic-embed-text-v1.5`, stores in ChromaDB. Skip re-embedding if nothing changed.
- **Chat with your codebase** — a ReAct agent powered by Groq, OpenRouter, or Anthropic that can semantically search the vector store, read files, grep, and explore the directory tree. Streaming responses with thinking visibility.
- **Repo insights** — an LLM agent explores the repo and returns a structured summary: purpose, tech stack, architecture, key files.
- **Charts & analytics** — language breakdown pie chart, dependency graph by ecosystem, contributor histogram with commit/additions/deletions, health score (stars/recency/issues/CI/tests/contributors/docs), codebase analytics (LOC, TODOs, complex/hot files, test coverage estimate).
- **Auto-generated documentation** — function/class summaries and API endpoint explorer, extracted by an LLM agent reading the source.
- **Session management** — persistent chat history per repo, stored in SQLite.

## Architecture

```
Frontend (React 19 + Vite + Tailwind CSS 4)
       │
       │ HTTP / SSE
       ▼
FastAPI Backend (Uvicorn)
       │
       ├── ChromaDB (vector store, on-disk)
       ├── SQLite (registry, sessions, insights, charts, docs)
       ├── Embeddings (HuggingFace, local CPU/GPU)
       ├── Reranker (CrossEncoder, local CPU)
       └── LLM APIs (Groq / OpenRouter / Anthropic — cloud only)
```

All ML models run locally (embedding + reranking). LLM inference is 100% cloud API calls — no GPU required for serving.

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

## Quick Start

### 1. Clone and set up the backend

```bash
git clone <repo-url> && cd Repo-Illustrator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env   # or create .env manually
```

Required variables (see [Environment Variables](#environment-variables) below).

### 3. Start the backend

```bash
uvicorn api.main:app --reload --reload-exclude "data/*" --reload-exclude "chroma_db/*"
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 4. Set up and run the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and connects to the backend at `http://localhost:8000`.

> Set `VITE_API_BASE_URL` in `frontend/.env` to change the backend URL.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes\* | — | Groq API key |
| `OPENROUTER_API_KEY` | Yes\* | — | OpenRouter API key |
| `ANTHROPIC_API_KEY` | Yes\* | — | Anthropic API key |
| `GITHUB_TOKEN` | No | — | GitHub token (increases rate limit to 5000 req/hr for contributor stats; also enables private repo cloning) |
| `GROQ_MODEL` | No | `llama3-70b-8192` | Default Groq model |
| `OPENROUTER_MODEL` | No | `deepseek/deepseek-v4-flash:free` | Default OpenRouter model |
| `ANTHROPIC_MODEL` | No | `claude-haiku-4-5-20251001` | Default Anthropic model |

\*At least one LLM provider key is required.

## API Endpoints

All endpoints are prefixed with `/repos`.

### Ingestion

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingest` | Ingest a repo by URL (runs in background) |
| `GET` | `/{repo_id}/status` | Check ingestion status |
| `GET` | `/` | List all ingested repos |
| `DELETE` | `/{repo_id}` | Delete repo (ChromaDB, disk, DB, caches) |

### Chat

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat/{repo_id}` | Send a message (sync response) |
| `POST` | `/chat/{repo_id}/stream` | Send a message (SSE streaming response) |
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

Full request/response schemas are in the interactive docs at `/docs` or in [`docs/api.md`](docs/api.md).

## Project Structure

```
.
├── api/                    # FastAPI application
│   ├── main.py             # App entry, lifespan, CORS, router registration
│   ├── database.py         # SQLite schema and CRUD
│   └── routes/
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
│       │   ├── Navbar.jsx
│       │   ├── Starfield.jsx
│       │   ├── FloatingWords.jsx
│       │   ├── SearchBar.jsx
│       │   └── ModeToggle.jsx
│       └── lib/
│           ├── api.jsx           # API client (all endpoints)
│           └── session.jsx       # Session ID persistence
├── data/                   # (gitignored) cloned & processed repos
├── chroma_db/              # (gitignored) vector index
├── repo_illustrator.db     # (gitignored) SQLite DB
├── requirements.txt
└── docs/api.md             # API documentation
```

## Troubleshooting

### `TypeError: argument 'source': 'bytes' object is not an instance of 'str'` (CodeSplitter / tree-sitter version conflict)

LlamaIndex's `CodeSplitter` has a known incompatibility with certain versions of `tree-sitter` related to a `bytes`/`str` API change introduced in `0.21+`. If you encounter this error, pin `tree-sitter==0.20.4` with individual language packages. If that fails, check the installed version of `llama-index-core` and match the tree-sitter version it expects.

### Embedding is slow on CPU

The embedding model (`nomic-embed-text-v1.5`) detects GPU automatically. On CPU-only machines (e.g. Oracle Free Tier), ingestion takes longer but works. This is a one-time cost per repo — subsequent reads use the cached index.

### Chat response is slow

The ReAct agent uses tool calls and multiple LLM rounds. For faster responses, use streaming (`POST /chat/{repo_id}/stream`) which shows thinking in real time.

## License

MIT
