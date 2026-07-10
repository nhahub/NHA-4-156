import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.database import get_repo_status, get_repo_chart, save_chart_status
from insights.provider import build_repo_insights
from insights.visualizer import build_chart_data

router = APIRouter()

VALID_PROVIDERS = {"groq", "openrouter", "anthropic"}


class ChartsRequest(BaseModel):
    provider: Optional[str] = "openrouter"
    model_name: Optional[str] = None


class ChartsStatusResponse(BaseModel):
    repo_id: str
    status: str
    last_updated: Optional[str] = None
    charts: Optional[dict] = None


async def _run_charts_job(repo_id: str, repo_url: str, provider: str, model_name: str):
    try:
        repo_insights = await build_repo_insights(
            repo_id=repo_id,
            repo_url=repo_url,
            provider=provider,
            model_name=model_name,
        )
        chart_data = build_chart_data(repo_insights)
        save_chart_status(repo_id, "ready", json.dumps(chart_data))
    except Exception as e:
        save_chart_status(repo_id, f"error: {str(e)}")


@router.post("/{repo_id}/charts")
async def start_charts(repo_id: str, background_tasks: BackgroundTasks, payload: ChartsRequest = ChartsRequest()):
    if payload.provider and payload.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider '{payload.provider}'. Must be one of: {', '.join(sorted(VALID_PROVIDERS))}",
        )

    repo_info = get_repo_status(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repo not found. Ingest it first.")
    if repo_info.get("status") != "ready":
        raise HTTPException(status_code=409, detail=f"Repo is not ready yet (status: {repo_info.get('status')}).")

    existing = get_repo_chart(repo_id)
    if existing and existing["status"] in ("processing", "ready"):
        return {
            "repo_id": repo_id,
            "status":  existing["status"],
            "message": f"Charts already {existing['status']}. Check GET /{repo_id}/charts for the result.",
        }

    repo_url = repo_info.get("url", "")
    save_chart_status(repo_id, "processing")
    background_tasks.add_task(_run_charts_job, repo_id, repo_url, payload.provider or "openrouter", payload.model_name)

    return {
        "repo_id": repo_id,
        "status":  "processing",
        "message": f"Chart generation started. Check status with GET /{repo_id}/charts",
    }


@router.get("/{repo_id}/charts", response_model=ChartsStatusResponse)
async def get_charts(repo_id: str):
    cached = get_repo_chart(repo_id)
    if not cached:
        raise HTTPException(status_code=404, detail="No charts found. Start one with POST /{repo_id}/charts.")

    charts = None
    if cached["status"] == "ready" and cached["chart_json"]:
        charts = json.loads(cached["chart_json"]).get("charts")

    return ChartsStatusResponse(
        repo_id=repo_id,
        status=cached["status"],
        last_updated=cached["last_updated"],
        charts=charts,
    )