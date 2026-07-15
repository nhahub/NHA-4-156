import asyncio
import threading
from fastapi import APIRouter, Request, HTTPException, Depends
from pathlib import Path
from pydantic import BaseModel, HttpUrl, field_validator
import re
from urllib.parse import urlparse
from ingestion import pipeline
from ingestion.preprocessor import force_rmtree, redact_credentials
from ingestion.exceptions import IngestionCancelled
from api.database import save_repo_status, get_repo_status, delete_repo_registry, invalidate_repo_insight, invalidate_repo_chart, invalidate_repo_docs, grant_repo_access, list_visible_repos
from api.auth import get_current_user, require_repo_access, parse_owner_repo, probe_repo_access, User
from vectorstore.chroma_store import RepoVectorStore

router = APIRouter()

class IndexRequest(BaseModel):
    repo_url: HttpUrl

    @field_validator("repo_url", mode="before")
    @classmethod
    def _ensure_scheme(cls, v):
        # Accept pasted links without a scheme (e.g. "github.com/owner/repo").
        # HttpUrl rejects those, which surfaced as a confusing 422; prepend
        # https:// before validation. Also fixes generate_repo_id(), whose
        # urlparse() needs the scheme to split netloc from path.
        if isinstance(v, str):
            v = v.strip()
            if v and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", v):
                v = "https://" + v
        return v

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

def process_repo(repo_id: str, repo_url: str, state, stop_event: threading.Event, github_token: str = None):
    ingest_pipeline = pipeline.IngestionPipeline()
    try:
        index, was_updated = ingest_pipeline.run(repo_url, repo_id, stop_event=stop_event, github_token=github_token)
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
        # The clone URL carries the user's OAuth token, so any git error text can
        # contain it. This status string is served by /status and rendered in the
        # UI — scrub credentials before it is persisted.
        save_repo_status(repo_id, repo_url, f"error: {redact_credentials(str(e))}")
    finally:
        if hasattr(state, 'stop_events'):
            state.stop_events.pop(repo_id, None)

@router.post("/ingest")
async def ingest_repository(request: Request, payload: IndexRequest, user: User | None = Depends(get_current_user)):
    repo_url = str(payload.repo_url)
    repo_id = generate_repo_id(repo_url)

    # Detect visibility + required token. We probe GitHub with the user's token
    # (if logged in) so private repos the user can see resolve as private.
    owner_repo = parse_owner_repo(repo_url)
    user_token = user.github_token if user else None

    visibility = "public"
    clone_token = None  # None = fall back to env GITHUB_TOKEN (or anonymous)

    if owner_repo:
        owner, name = owner_repo
        accessible, is_private, probe_status = await probe_repo_access(owner, name, user_token)
        if not accessible:
            if user is None:
                raise HTTPException(
                    status_code=401,
                    detail="This repository is private or does not exist. "
                           "If it's a private repo you have access to, sign in with GitHub first.",
                )
            if probe_status == 401:
                # Token is actually invalid/expired — clear it so the user re-logins.
                from api import database
                database.clear_user_token(user.id)
                raise HTTPException(
                    status_code=401,
                    detail="Your GitHub token has expired. Please sign in again.",
                )
            # 404 or other: repo doesn't exist or user isn't a collaborator.
            # Don't destroy a valid token.
            raise HTTPException(
                status_code=403,
                detail="This repository is private or does not exist, and your "
                       "GitHub account doesn't have access to it.",
            )
        if is_private:
            visibility = "private"
            # Private repos MUST use the user's token — env token won't have access.
            if not user_token:
                raise HTTPException(status_code=401, detail="Private repo detected but no user token. Sign in with GitHub.")
            clone_token = user_token
        else:
            # Public repo: prefer env GITHUB_TOKEN for rate-limit headroom; the
            # preprocessor falls back to it when github_token is None.
            clone_token = None

    # Already ingested? Fast path: grant access and return immediately.
    existing = get_repo_status(repo_id)
    if existing and existing.get("status") == "ready":
        if visibility == "private" and user is not None:
            grant_repo_access(repo_id, user.id, "collaborator" if existing.get("owner_user_id") != user.id else "owner")
        return {
            "repo_id": repo_id,
            "status": "ready",
            "message": f"Repository already ingested. Open /repo/{repo_id}/illustration",
        }

    state = request.app.state
    if not hasattr(state, 'stop_events'):
        state.stop_events = {}
    stop_event = threading.Event()
    state.stop_events[repo_id] = stop_event

    save_repo_status(repo_id, repo_url, "processing")
    # Persist visibility + ownership immediately so status checks see it.
    from api.database import save_repo_visibility
    save_repo_visibility(repo_id, visibility, owner_user_id=user.id if user else None)
    if visibility == "private" and user is not None:
        grant_repo_access(repo_id, user.id, "owner")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, process_repo, repo_id, repo_url, state, stop_event, clone_token)

    return {"repo_id": repo_id, "message": f"Ingestion started. Check status with GET /{repo_id}/status"}

@router.post("/{repo_id}/stop")
async def stop_ingestion(repo_id: str, request: Request, user: User | None = Depends(get_current_user)):
    # Only the owner (or anyone for public repos) may stop an in-progress ingestion.
    repo_info = get_repo_status(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if (repo_info.get("visibility") or "public") == "private":
        if user is None or (repo_info.get("owner_user_id") != user.id and not _is_owner(repo_id, user)):
            raise HTTPException(status_code=403, detail="Only the repo owner can stop ingestion of a private repo.")

    state = request.app.state
    stop_events = getattr(state, 'stop_events', {})
    stop_event = stop_events.get(repo_id)

    if stop_event is None:
        raise HTTPException(
            status_code=404,
            detail="No in-progress ingestion found for this repository (it may have already finished or been stopped).",
        )

    stop_event.set()
    save_repo_status(repo_id, repo_info.get("url", ""), "cancelling")

    return {"repo_id": repo_id, "message": "Stop requested. Ingestion will cancel and clean up shortly."}

def _is_owner(repo_id: str, user: User) -> bool:
    from api.database import has_repo_access
    return has_repo_access(repo_id, user.id)

@router.get("/{repo_id}/status")
async def get_status_endpoint(repo_id: str, request: Request, user: User | None = Depends(get_current_user)):
    repo_info = get_repo_status(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repository ID not found")

    # Authorize: private repos require access.
    await require_repo_access(repo_id, user)

    return {
        "repo_id": repo_id,
        "url": repo_info.get("url", "unknown"),
        "status": repo_info.get("status", "ready (loaded from disk)"),
        "visibility": repo_info.get("visibility", "public"),
    }

@router.delete("/{repo_id}")
async def delete_repository(repo_id: str, request: Request, user: User | None = Depends(get_current_user)):
    repo_info = get_repo_status(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Delete is owner-only for private repos; public repos allow anyone (demo behavior).
    visibility = repo_info.get("visibility") or "public"
    if visibility == "private":
        if user is None or repo_info.get("owner_user_id") != user.id:
            raise HTTPException(status_code=403, detail="Only the repo owner can delete a private repo.")

    _cleanup_repo_artifacts(repo_id)
    delete_repo_registry(repo_id)
    _clear_repo_caches(repo_id, request.app.state)

    return {"message": f"Repository {repo_id} deleted successfully"}

@router.get("/")
async def list_repositories(user: User | None = Depends(get_current_user)):
    try:
        repos = list_visible_repos(user.id if user else None)
        return {"repositories": repos}
    except Exception as e:
        print(f"[list_repositories] raw error: {e}")  # detail stays in server logs
        raise HTTPException(status_code=500, detail="Failed to retrieve repositories.")
