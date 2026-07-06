from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from llama_index.core import Settings
from embeddings.embedder import RepoEmbedder
from api.routes import chat, ingestion, insight, charts
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
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router, prefix="/repos", tags=["Ingestion"])
app.include_router(chat.router, prefix="/repos", tags=["Chat"])
app.include_router(insight.router, prefix="/repos", tags=["Insight"])
app.include_router(insight.router, prefix="/repos", tags=["Insight"])
app.include_router(charts.router, prefix="/repos", tags=["Charts"])