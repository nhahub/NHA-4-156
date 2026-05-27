from fastapi import FastAPI, HTTPException, BackgroundTasks
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from llama_index.core import Settings
from embeddings.embedder import RepoEmbedder
from api.routes import chat, ingestion
from api.registry import load_registry

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()

    # Configure LlamaIndex settings globally
    Settings.chunk_size = 512
    Settings.chunk_overlap = 50
    Settings.embed_model = RepoEmbedder().get_embed_model()

    app.state.repo_dict = load_registry()
    app.state.index_cache = {}
    app.state.sessions = {}
    
    yield

    del app.state.repo_dict
    del app.state.index_cache
    del app.state.sessions

app = FastAPI(lifespan=lifespan, title="Repo Illustrator API")
app.include_router(ingestion.router, prefix="/repos", tags=["Ingestion"])
app.include_router(chat.router, prefix="/repos", tags=["Chat"])
