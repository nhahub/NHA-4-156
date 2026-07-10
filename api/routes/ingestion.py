import asyncio
import threading
from fastapi import APIRouter, Request, HTTPException
from pathlib import Path
from pydantic import BaseModel, HttpUrl
import re
from urllib.parse import urlparse
from ingestion import pipeline
from ingestion.preprocessor import force_rmtree
from ingestion.exceptions import IngestionCancelled
from api.database import get_all_repos, save_repo_status, get_repo_status, delete_repo_registry, invalidate_repo_insight, invalidate_repo_chart, invalidate_repo_docs
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

def _cleanup_repo_artifacts(repo_id: str):
    try:
        store = RepoVectorStore(collection_name=repo_id)
        store.delete_permanently()
    except Exception as e:
        print(f"ChromaDB cleanup note: {e}")

    processed_path = Path("data/processed") / repo_id
    if processed_path.exists():
        force_rmtree(processed_path)

    raw_path = Path("data/raw") / repo_id
    if raw_path.exists():
        force_rmtree(raw_path)

def _clear_repo_caches(repo_id: str, state):
    if hasattr(state, 'index_cache') and repo_id in state.index_cache:
        del state.index_cache[repo_id]
    if hasattr(state, 'agent_cache'):
        keys_to_remove = [k for k in state.agent_cache if k.endswith(f":{repo_id}")]
        for k in keys_to_remove:
            del state.agent_cache[k]

def process_repo(repo_id: str, repo_url: str, state, stop_event: threading.Event):
    ingest_pipeline = pipeline.IngestionPipeline()
    try:
        index, was_updated = ingest_pipeline.run(repo_url, repo_id, stop_event=stop_event)
        save_repo_status(repo_id, repo_url, "ready", repo_id)
        state.index_cache[repo_id] = index
        if was_updated:
            invalidate_repo_insight(repo_id)
            #added invalidate chart + document too
            invalidate_repo_chart(repo_id)
            invalidate_repo_docs(repo_id)
            if hasattr(state, 'agent_cache'):
                keys_to_remove = [k for k in state.agent_cache if k.endswith(f":{repo_id}")]
                for k in keys_to_remove:
                    del state.agent_cache[k]
    except IngestionCancelled:
        print(f"Ingestion for '{repo_id}' was cancelled by user. Cleaning up.")
        _cleanup_repo_artifacts(repo_id)
        delete_repo_registry(repo_id)
        _clear_repo_caches(repo_id, state)
    except Exception as e:
        save_repo_status(repo_id, repo_url, f"error: {str(e)}")
    finally:
        if hasattr(state, 'stop_events'):
            state.stop_events.pop(repo_id, None)

@router.post("/ingest")
async def ingest_repository(request: Request, payload: IndexRequest):
    repo_url = str(payload.repo_url)
    repo_id = generate_repo_id(repo_url)

    state = request.app.state
    if not hasattr(state, 'stop_events'):
        state.stop_events = {}
    stop_event = threading.Event()
    state.stop_events[repo_id] = stop_event

    save_repo_status(repo_id, repo_url, "processing")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, process_repo, repo_id, repo_url, state, stop_event)

    return {"repo_id": repo_id, "message": f"Ingestion started. Check status with GET /{repo_id}/status"}

@router.post("/{repo_id}/stop")
async def stop_ingestion(repo_id: str, request: Request):
    state = request.app.state
    stop_events = getattr(state, 'stop_events', {})
    stop_event = stop_events.get(repo_id)

    if stop_event is None:
        raise HTTPException(
            status_code=404,
            detail="No in-progress ingestion found for this repository (it may have already finished or been stopped).",
        )

    stop_event.set()
    save_repo_status(repo_id, "", "cancelling")

    return {"repo_id": repo_id, "message": "Stop requested. Ingestion will cancel and clean up shortly."}

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

    _cleanup_repo_artifacts(repo_id)
    delete_repo_registry(repo_id)
    _clear_repo_caches(repo_id, request.app.state)

    return {"message": f"Repository {repo_id} deleted successfully"}

@router.get("/")
async def list_repositories():
    try:
        repos = get_all_repos()
        return {"repositories": repos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve repositories: {str(e)}")