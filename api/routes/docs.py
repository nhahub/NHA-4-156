import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.database import get_repo_status, get_repo_docs, save_docs_status
from insights.document_generator import generate_docs

router = APIRouter()

VALID_PROVIDERS = {"groq", "openrouter"}


class DocsRequest(BaseModel):
    provider: Optional[str] = "groq"
    model_name: Optional[str] = None


class DocsStatusResponse(BaseModel):
    repo_id: str
    status: str
    last_updated: Optional[str] = None
    docs: Optional[dict] = None


async def _run_docs_job(repo_id: str, provider: str, model_name: str):
    try:
        docs = await generate_docs(repo_id=repo_id, provider=provider, model_name=model_name)
        save_docs_status(repo_id, "ready", json.dumps(docs))
    except Exception as e:
        save_docs_status(repo_id, f"error: {str(e)}")


@router.post("/{repo_id}/docs")
async def start_docs(repo_id: str, background_tasks: BackgroundTasks, payload: DocsRequest = DocsRequest()):
    if payload.provider and payload.provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider '{payload.provider}'.")

    repo_info = get_repo_status(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repo not found. Ingest it first.")
    if repo_info.get("status") != "ready":
        raise HTTPException(status_code=409, detail=f"Repo is not ready yet (status: {repo_info.get('status')}).")

    existing = get_repo_docs(repo_id)
    if existing and existing["status"] in ("processing", "ready"):
        return {
            "repo_id": repo_id,
            "status":  existing["status"],
            "message": f"Docs already {existing['status']}. Check GET /{repo_id}/docs for the result.",
        }

    save_docs_status(repo_id, "processing")
    background_tasks.add_task(_run_docs_job, repo_id, payload.provider or "groq", payload.model_name)

    return {
        "repo_id": repo_id,
        "status":  "processing",
        "message": f"Docs generation started. Check status with GET /{repo_id}/docs",
    }


@router.get("/{repo_id}/docs", response_model=DocsStatusResponse)
async def get_docs(repo_id: str):
    cached = get_repo_docs(repo_id)
    if not cached:
        raise HTTPException(status_code=404, detail="No docs found. Start one with POST /{repo_id}/docs.")

    docs = None
    if cached["status"] == "ready" and cached["docs_json"]:
        docs = json.loads(cached["docs_json"])

    return DocsStatusResponse(
        repo_id=repo_id,
        status=cached["status"],
        last_updated=cached["last_updated"],
        docs=docs,
    )