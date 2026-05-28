from fastapi import FastAPI, HTTPException, BackgroundTasks
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from llama_index.core import Settings
from embeddings.embedder import RepoEmbedder
from api.routes import chat, ingestion
from api.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()

    # Configure LlamaIndex settings globally
    Settings.chunk_size = 512
    Settings.chunk_overlap = 50
    Settings.embed_model = RepoEmbedder().get_embed_model()

    init_db()

    app.state.index_cache = {}
    
    yield

    del app.state.index_cache

app = FastAPI(lifespan=lifespan, title="Repo Illustrator API")
app.include_router(ingestion.router, prefix="/repos", tags=["Ingestion"])
app.include_router(chat.router, prefix="/repos", tags=["Chat"])
