from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from pydantic import BaseModel, HttpUrl
import re
from urllib.parse import urlparse
from ingestion import pipeline
from api.registry import save_registry

router = APIRouter()

class IndexRequest(BaseModel):
    repo_url: HttpUrl

def generate_repo_id(url: str) -> str:
    path = urlparse(url).path.strip('/')
    parts = path.split('/')
    if len(parts) >= 2:
        return f"{parts[0]}__{parts[1]}".lower().replace('-', '_')
    return re.sub(r'[^a-zA-Z0-9]', '_', path).lower()

def process_repo(repo_id: str, repo_url: str, state):
    ingest_pipeline = pipeline.IngestionPipeline()
    try:
        index = ingest_pipeline.run(repo_url, repo_id)
        state.repo_dict[repo_id] = {
            "url": repo_url,
            "collection_name": repo_id,
            "status": "ready"
        }
        state.index_cache[repo_id] = index
    except Exception as e:
        state.repo_dict[repo_id] = {
            "url": repo_url,
            "status": f"error: {str(e)}"
        }
    
    save_registry(state.repo_dict)

@router.post("/ingest")
async def ingest_repository(request: Request, payload: IndexRequest, background_tasks: BackgroundTasks):
    repo_url = str(payload.repo_url)
    repo_id = generate_repo_id(repo_url)
    
    request.app.state.repo_dict[repo_id] = {
        "url": repo_url,
        "status": "processing"
    }
    save_registry(request.app.state.repo_dict)

    background_tasks.add_task(process_repo, repo_id, repo_url, request.app.state)
    
    return {"repo_id": repo_id, "message": f"Ingestion started. Check status with GET /{repo_id}/status"}

@router.get("/{repo_id}/status")
async def get_repo_status(repo_id: str, request: Request):
    repo_info = request.app.state.repo_dict.get(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repository ID not found")
    
    return {
        "repo_id": repo_id,
        "url": repo_info.get("url", "unknown"),
        "status": repo_info.get("status", "ready (loaded from disk)")
    }