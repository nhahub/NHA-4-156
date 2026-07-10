from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from llama_index.core import Settings
from embeddings.embedder import RepoEmbedder
from api.routes import chat, ingestion, insight, charts, docs
from api.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()

    Settings.chunk_size = 512
    Settings.chunk_overlap = 50
    Settings.embed_model = RepoEmbedder().get_embed_model()

    init_db()

    app.state.index_cache = {}
    app.state.agent_cache = {}
    yield

    del app.state.index_cache
    del app.state.agent_cache

app = FastAPI(lifespan=lifespan, title="Repo Illustrator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router, prefix="/repos", tags=["Ingestion"])
app.include_router(chat.router, prefix="/repos", tags=["Chat"])
app.include_router(insight.router, prefix="/repos", tags=["Insight"])
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
        if full_path.startswith("repos") or full_path in ("docs", "openapi.json", "redoc"):
            raise HTTPException(status_code=404)
        index_file = STATIC_DIR / "index.html"
        return FileResponse(index_file)