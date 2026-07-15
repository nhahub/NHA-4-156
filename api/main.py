from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
import os
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from llama_index.core import Settings
from embeddings.provider import get_embedder
from api.routes import auth, chat, ingestion, insight, charts, docs
from api.database import init_db

# Must run before any module-level os.getenv() below — the session secret, CORS
# origins and cookie flags are all read at import time, long before lifespan().
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Settings.chunk_size = 512
    Settings.chunk_overlap = 50
    Settings.embed_model = get_embedder(provider=os.getenv("EMBEDDING_PROVIDER", "local"))

    init_db()

    app.state.index_cache = {}
    app.state.agent_cache = {}
    yield

    del app.state.index_cache
    del app.state.agent_cache

app = FastAPI(lifespan=lifespan, title="Repo Illustrator API")

# Signed-cookie sessions. SECRET_KEY must be set in .env (any long random string).
_session_secret = os.getenv("SESSION_SECRET_KEY") or os.getenv("SECRET_KEY")
if not _session_secret:
    # Fallback so dev works without configuration; production MUST set it.
    _session_secret = "dev-only-insecure-session-secret-change-me"
    print("[WARNING] SESSION_SECRET_KEY not set — using insecure dev default. Set it in .env for production.")
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    # Browser-session cookie (cleared on close) per the agreed plan.
    # Set SESSION_COOKIE_MAX_AGE=2592000 in .env for a 30-day "remember me" later.
    max_age=int(os.getenv("SESSION_COOKIE_MAX_AGE", "0")) or None,
    same_site="lax",
    https_only=os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
    session_cookie="repo_illustrator_session",
)

# CORS: must be explicit origins (not "*") because we now send credentials.
_cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "")
if _cors_raw:
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    # Same-origin in the Docker single-port deployment; local Vite dev adds its origin.
    _cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth routes are NOT under /repos — they sit at /auth/...
app.include_router(auth.router, tags=["Auth"])
app.include_router(ingestion.router, prefix="/repos", tags=["Ingestion"])
app.include_router(chat.router, prefix="/repos", tags=["Chat"])
app.include_router(insight.router, prefix="/repos", tags=["Insights"])
app.include_router(charts.router, prefix="/repos", tags=["Charts"])
app.include_router(docs.router, prefix="/repos", tags=["Docs"])

# ---------------------------------------------------------------
# Serve the built React frontend (only present inside the Docker
# image — locally you still run `npm run dev` separately).
# ---------------------------------------------------------------
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        # never swallow API routes or the FastAPI docs UI
        if full_path.startswith("repos") or full_path.startswith("auth") or full_path in ("docs", "openapi.json", "redoc"):
            raise HTTPException(status_code=404)
        index_file = STATIC_DIR / "index.html"
        return FileResponse(index_file)
