import json
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from pydantic import BaseModel

from api.database import get_repo_status, get_repo_insight, save_insight_status
from rag.insight_generator import generate_insight

router = APIRouter()

VALID_PROVIDERS = {"groq", "openrouter"}


class InsightRequest(BaseModel):
    provider: Optional[str] = "groq"
    model_name: Optional[str] = None


class KeyFile(BaseModel):
    path: str
    purpose: str


class InsightResult(BaseModel):
    purpose: str = ""
    tech_stack: List[str] = []
    architecture: str = ""
    key_files: List[KeyFile] = []
    parse_warning: Optional[str] = None


class InsightStatusResponse(BaseModel):
    repo_id: str
    status: str
    last_updated: Optional[str] = None
    result: Optional[InsightResult] = None


async def _run_insight_job(repo_id: str, provider: str, model_name: str):
    try:
        repo_path = f"data/processed/{repo_id}"
        data = await generate_insight(
            repo_path=repo_path,
            provider=provider,
            model_name=model_name,
        )
        save_insight_status(repo_id, "ready", json.dumps(data))
    except Exception as e:
        save_insight_status(repo_id, f"error: {str(e)}")


@router.post("/{repo_id}/insight")
async def start_insight(
    repo_id: str,
    background_tasks: BackgroundTasks,
    payload: InsightRequest = InsightRequest(),
):
    if payload.provider and payload.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider '{payload.provider}'. Must be one of: {', '.join(sorted(VALID_PROVIDERS))}",
        )

    repo_info = get_repo_status(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repo metadata not found. Ingest the repo first.")
    if repo_info.get("status") != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Repo is not ready yet (status: {repo_info.get('status')}).",
        )

    existing = get_repo_insight(repo_id)
    if existing and existing["status"] in ("processing", "ready"):
        return {
            "repo_id": repo_id,
            "status": existing["status"],
            "message": f"Insight already {existing['status']}. Check GET /{repo_id}/insight for the result.",
        }

    save_insight_status(repo_id, "processing")
    background_tasks.add_task(
        _run_insight_job, repo_id, payload.provider, payload.model_name
    )

    return {
        "repo_id": repo_id,
        "status": "processing",
        "message": f"Insight generation started. Check status with GET /{repo_id}/insight",
    }


@router.get("/{repo_id}/insight", response_model=InsightStatusResponse)
async def get_insight(repo_id: str):
    cached = get_repo_insight(repo_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail="No insight found for this repo. Start one with POST /{repo_id}/insight.",
        )

    result = None
    if cached["status"] == "ready" and cached["insight_json"]:
        result = InsightResult(**json.loads(cached["insight_json"]))

    return InsightStatusResponse(
        repo_id=repo_id,
        status=cached["status"],
        last_updated=cached["last_updated"],
        result=result,
    )