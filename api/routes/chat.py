import json
import uuid
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llm.chatbot import Chatbot, friendly_error_message
from rag.engine import load_repo_index
from api.database import get_repo_status, get_session, save_session, delete_session, list_user_sessions
from api.auth import require_user, require_repo_access, require_session_owner, User
from llama_index.core.llms import ChatMessage, MessageRole

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    provider: Optional[str] = "openrouter"
    model_name: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

VALID_PROVIDERS = {"groq", "openrouter", "anthropic"}


def _error_status_code(e: Exception) -> int:
    text = str(e)
    lower = text.lower()
    if "rate_limit_exceeded" in lower or "rate limit" in lower or "429" in text:
        return 429
    if "401" in text or "unauthorized" in lower or "invalid api key" in lower:
        return 401
    if "503" in text or "service unavailable" in lower:
        return 503
    return 500


async def _get_or_create_chatbot(repo_id: str, session_id: str, provider: str, model_name: str, app_state, user: User | None = None):
    if hasattr(app_state, 'index_cache') and repo_id in app_state.index_cache:
        index = app_state.index_cache[repo_id]
    else:
        repo_info = get_repo_status(repo_id)
        if not repo_info:
            raise HTTPException(status_code=404, detail="Repo metadata not found. Ingest the repo first.")
        collection_name = repo_info.get("collection_name") or repo_id
        index = load_repo_index(collection_name)
        if not hasattr(app_state, 'index_cache'):
            app_state.index_cache = {}
        app_state.index_cache[repo_id] = index

    if not session_id:
        session_id = str(uuid.uuid4())

    # Ownership check: if the session already exists, it must belong to this user.
    # A brand-new session_id (no row yet) is allowed — it gets stamped with the
    # user's id on the first save_session() call.
    from api.database import get_session_meta
    meta = get_session_meta(session_id)
    if meta is not None and user is not None and meta.get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Session not found.")
    if meta is not None and meta.get("repo_id") and meta["repo_id"] != repo_id:
        raise HTTPException(status_code=404, detail="Session not found.")

    raw_history = get_session(session_id) or []
    history = [ChatMessage(role=MessageRole(msg["role"]), content=msg["content"]) for msg in raw_history]

    repo_path = f"data/processed/{repo_id}"

    cache_key = f"{session_id}:{repo_id}"
    if hasattr(app_state, 'agent_cache') and cache_key in app_state.agent_cache:
        chatbot = app_state.agent_cache[cache_key]
    else:
        chatbot = Chatbot(index=index, repo_path=repo_path, provider=provider, model_name=model_name)
        chatbot.get_chat_engine(history=history)
        if not hasattr(app_state, 'agent_cache'):
            app_state.agent_cache = {}
        app_state.agent_cache[cache_key] = chatbot

    return chatbot, session_id


@router.post("/chat/{repo_id}", response_model=ChatResponse)
async def chat(repo_id: str, request: Request, payload: ChatRequest, user: User = Depends(require_user)):
    if payload.provider and payload.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider '{payload.provider}'. Must be one of: {', '.join(sorted(VALID_PROVIDERS))}"
        )

    # Authorize repo access first (raises 404/401/403).
    await require_repo_access(repo_id, user)

    try:
        chatbot, session_id = await _get_or_create_chatbot(
            repo_id, payload.session_id or "", payload.provider, payload.model_name, request.app.state, user
        )
        response = await chatbot.chat(payload.message)
        save_session(session_id, chatbot.chat_history, user_id=user.id, repo_id=repo_id)
        return ChatResponse(response=response.response, session_id=session_id)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[chat] raw error: {e}")  # full detail stays in server logs
        raise HTTPException(status_code=_error_status_code(e), detail=friendly_error_message(e))


@router.post("/chat/{repo_id}/stream")
async def chat_stream(repo_id: str, request: Request, payload: ChatRequest, user: User = Depends(require_user)):
    if payload.provider and payload.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider '{payload.provider}'. Must be one of: {', '.join(sorted(VALID_PROVIDERS))}"
        )

    # Authorize repo access first.
    await require_repo_access(repo_id, user)

    try:
        chatbot, session_id = await _get_or_create_chatbot(
            repo_id, payload.session_id or "", payload.provider, payload.model_name, request.app.state, user
        )

        async def event_generator():
            try:
                async for event in chatbot.chat_stream(payload.message):
                    yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
            finally:
                save_session(session_id, chatbot.chat_history, user_id=user.id, repo_id=repo_id)

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[chat_stream] raw error: {e}")  # full detail stays in server logs
        raise HTTPException(status_code=_error_status_code(e), detail=friendly_error_message(e))

@router.delete("/chat/{session_id}")
async def delete_chat_session(session_id: str, request: Request, user: User = Depends(require_user)):
    require_session_owner(session_id, user)
    try:
        delete_session(session_id)
        app_state = request.app.state
        if hasattr(app_state, 'agent_cache'):
            keys_to_remove = [k for k in app_state.agent_cache if k.startswith(f"{session_id}:")]
            for k in keys_to_remove:
                del app_state.agent_cache[k]
        return {"message": f"Session {session_id} deleted successfully."}
    except Exception as e:
        print(f"[delete_chat_session] raw error: {e}")  # detail stays in server logs
        raise HTTPException(status_code=500, detail="Could not delete this session. Please try again.")

@router.get("/chat/{session_id}/history")
async def get_chat_history(session_id: str, user: User = Depends(require_user)):
    # If the session doesn't exist yet (first visit, or wiped), return empty
    # history instead of 404 — the frontend treats this as "no prior conversation".
    raw_history = get_session(session_id)
    if raw_history is None:
        return {"session_id": session_id, "history": []}

    # Session exists — verify the caller owns it.
    require_session_owner(session_id, user)

    try:
        history = [{"role": msg["role"], "content": msg["content"]} for msg in raw_history]
        return {"session_id": session_id, "history": history}
    except Exception as e:
        print(f"[get_chat_history] raw error: {e}")  # detail stays in server logs
        raise HTTPException(status_code=500, detail="Could not load chat history. Please try again.")

@router.get("/chat/{repo_id}/sessions")
async def list_sessions(repo_id: str, user: User = Depends(require_user)):
    """List the current user's chat sessions for a repo."""
    await require_repo_access(repo_id, user)
    sessions = list_user_sessions(user.id, repo_id=repo_id)
    return {"repo_id": repo_id, "sessions": sessions}