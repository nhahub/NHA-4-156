from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from llm.chatbot import Chatbot
from rag.engine import load_repo_index  # Assume your teammate built this

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    provider: Optional[str] = "groq"
    model_name: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

@router.post("/chat/{repo_id}", response_model=ChatResponse)
async def chat(repo_id: str, request: Request, payload: ChatRequest):
    app_state = request.app.state
    
    if hasattr(app_state, 'index_cache') and repo_id in app_state.index_cache:
        index = app_state.index_cache[repo_id]
    else:
        repo_info = app_state.repo_dict.get(repo_id)
        if not repo_info:
            raise HTTPException(status_code=404, detail="Repo metadata not found. Ingest the repo first.")
            
        try:
            collection_name = repo_info.get("collection_name", repo_id)
            index = load_repo_index(collection_name)
            if not hasattr(app_state, 'index_cache'):
                app_state.index_cache = {}
            app_state.index_cache[repo_id] = index
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Repo index not found: {str(e)}. Ingest the repo first.")
        
    session_id = payload.session_id or str(uuid.uuid4())
    if session_id not in app_state.sessions:
        app_state.sessions[session_id] = []
    
    history = app_state.sessions[session_id]
    try: 
        chatbot = Chatbot(index=index, provider=payload.provider, model_name=payload.model_name)
        chat_engine = chatbot.get_chat_engine(history=history)
        response = chat_engine.chat(payload.message)
        app_state.sessions[session_id] = chat_engine.chat_history

        return ChatResponse(response=str(response), session_id=session_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occurred while processing chat message: {str(e)}")