import json
import uuid
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llm.chatbot import Chatbot, friendly_error_message
from rag.engine import load_repo_index  
from api.database import get_repo_status, get_session, save_session, delete_session
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

VALID_PROVIDERS = {"groq", "openrouter"}


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


async def _get_or_create_chatbot(repo_id: str, session_id: str, provider: str, model_name: str, app_state):
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
async def chat(repo_id: str, request: Request, payload: ChatRequest):
    if payload.provider and payload.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider '{payload.provider}'. Must be one of: {', '.join(sorted(VALID_PROVIDERS))}"
        )

    try:
        chatbot, session_id = await _get_or_create_chatbot(
            repo_id, payload.session_id or "", payload.provider, payload.model_name, request.app.state
        )
        response = await chatbot.chat(payload.message)
        save_session(session_id, chatbot.chat_history)
        return ChatResponse(response=response.response, session_id=session_id)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[chat] raw error: {e}")  # full detail stays in server logs
        raise HTTPException(status_code=_error_status_code(e), detail=friendly_error_message(e))


@router.post("/chat/{repo_id}/stream")
async def chat_stream(repo_id: str, request: Request, payload: ChatRequest):
    if payload.provider and payload.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider '{payload.provider}'. Must be one of: {', '.join(sorted(VALID_PROVIDERS))}"
        )

    try:
        chatbot, session_id = await _get_or_create_chatbot(
            repo_id, payload.session_id or "", payload.provider, payload.model_name, request.app.state
        )

        async def event_generator():
            try:
                async for event in chatbot.chat_stream(payload.message):
                    yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
            finally:
                save_session(session_id, chatbot.chat_history)

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[chat_stream] raw error: {e}")  # full detail stays in server logs
        raise HTTPException(status_code=_error_status_code(e), detail=friendly_error_message(e))
    
@router.delete("/chat/{session_id}")
async def delete_chat_session(session_id: str, request: Request):
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        delete_session(session_id)
        app_state = request.app.state
        if hasattr(app_state, 'agent_cache'):
            keys_to_remove = [k for k in app_state.agent_cache if k.startswith(f"{session_id}:")]
            for k in keys_to_remove:
                del app_state.agent_cache[k]
        return {"message": f"Session {session_id} deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occurred while deleting session: {str(e)}")
    
@router.get("/chat/{session_id}/history")
async def get_chat_history(session_id: str):
    raw_history = get_session(session_id)
    if raw_history is None:
            raise HTTPException(status_code=404, detail="Session not found")
    try:
        history = [{"role": msg["role"], "content": msg["content"]} for msg in raw_history]
        return {"session_id": session_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occurred while retrieving chat history: {str(e)}")