from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from pydantic import BaseModel, HttpUrl
import uuid

router = APIRouter()

class IndexRequest(BaseModel):
    repo_url: HttpUrl

def process_repo(repo_id: str, repo_url: str, state):
    pipeline = state.pipeline
    try:
        index = pipeline.run(repo_url)
        state.repo_dict[repo_id] = {
            "url": repo_url,
            "index": index,
            "status": "ready"
        }
    except Exception as e:
        state.repo_dict[repo_id] = {
            "url": repo_url,
            "index": None,
            "status": f"error: {str(e)}"
        }

@router.post("/ingest")
async def ingest_repository(request: Request, payload: IndexRequest, background_tasks: BackgroundTasks):
    repo_id = str(uuid.uuid4()) #TODO: this should be repo author + name or similar
    repo_url = str(payload.repo_url)
    
    request.app.state.repo_dict[repo_id] = {
        "url": repo_url,
        "index": None,
        "status": "processing"
    }

    background_tasks.add_task(process_repo, repo_id, repo_url, request.app.state)
    
    return {"repo_id": repo_id, "message": "Ingestion started. Check status with GET /{repo_id}/status"}

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