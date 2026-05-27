from fastapi import FastAPI, HTTPException, BackgroundTasks
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from ingestion import pipeline
from api.routes import chat, ingestion

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()

    app.state.pipeline = pipeline.IngestionPipeline()

    app.state.repo_dict = {}
    app.state.sessions = {}
    # any extra llm api initialization can go here
    
    yield

    del app.state.pipeline
    del app.state.repo_dict
    del app.state.sessions

app = FastAPI(lifespan=lifespan, title="Repo Illustrator API")
app.include_router(ingestion.router, prefix="/repos", tags=["Ingestion"])
app.include_router(chat.router, prefix="/repos", tags=["Chat"])
