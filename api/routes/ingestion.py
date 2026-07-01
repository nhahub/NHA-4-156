import shutil
import sqlite3
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from pathlib import Path
from pydantic import BaseModel, HttpUrl
import re
from urllib.parse import urlparse
from ingestion import pipeline
from api.database import get_all_repos, save_repo_status, get_repo_status, delete_repo_registry, invalidate_repo_insight
from vectorstore.chroma_store import RepoVectorStore

router = APIRouter()

class IndexRequest(BaseModel):
    repo_url: HttpUrl

def generate_repo_id(url: str) -> str:
    path = urlparse(url).path.strip('/')
    parts = path.split('/')
    if len(parts) >= 2:
        repo = parts[1].replace('.git', '')
        return f"{parts[0]}__{repo}".lower().replace('-', '_')
    return re.sub(r'[^a-zA-Z0-9]', '_', path.replace('.git', '')).lower()

def process_repo(repo_id: str, repo_url: str, state):
    ingest_pipeline = pipeline.IngestionPipeline()
    try:
        index, was_updated = ingest_pipeline.run(repo_url, repo_id)
        save_repo_status(repo_id, repo_url, "ready", repo_id)
        state.index_cache[repo_id] = index
        if was_updated:
            invalidate_repo_insight(repo_id)
    except Exception as e:
        save_repo_status(repo_id, repo_url, f"error: {str(e)}")

@router.post("/ingest")
async def ingest_repository(request: Request, payload: IndexRequest, background_tasks: BackgroundTasks):
    repo_url = str(payload.repo_url)
    repo_id = generate_repo_id(repo_url)
    
    save_repo_status(repo_id, repo_url, "processing")

    background_tasks.add_task(process_repo, repo_id, repo_url, request.app.state)
    
    return {"repo_id": repo_id, "message": f"Ingestion started. Check status with GET /{repo_id}/status"}

@router.get("/{repo_id}/status")
async def get_status_endpoint(repo_id: str):
    repo_info = get_repo_status(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repository ID not found")
    
    return {
        "repo_id": repo_id,
        "url": repo_info.get("url", "unknown"),
        "status": repo_info.get("status", "ready (loaded from disk)")
    }

@router.delete("/{repo_id}")
async def delete_repository(repo_id: str, request: Request):
    repo_info = get_repo_status(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Remove from ChromaDB
    try:
        store = RepoVectorStore(collection_name=repo_id)
        store.client.delete_collection(name=repo_id)
    except Exception as e:
        print(f"ChromaDB cleanup note: {e}")

    # Remove processed data from disk
    processed_path = Path("data/processed") / repo_id
    if processed_path.exists():
        shutil.rmtree(processed_path)

    # Remove raw cloned data from disk
    raw_path = Path("data/raw") / repo_id
    if raw_path.exists():
        shutil.rmtree(raw_path)

    # Remove from database
    delete_repo_registry(repo_id)

    # Clear index cache
    app_state = request.app.state
    if hasattr(app_state, 'index_cache') and repo_id in app_state.index_cache:
        del app_state.index_cache[repo_id]

    return {"message": f"Repository {repo_id} deleted successfully"}

@router.get("/")
async def list_repositories():
    try:
        repos = get_all_repos()
        return {"repositories": repos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve repositories: {str(e)}")