import os
from llama_index.core import VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent

def llm_provider(provider : str = "groq", model_name : str = None, temperature : float = 0.7):
    if provider == "groq":
        from llama_index.llms.groq import Groq
        model = model_name or "llama-3.3-70b-versatile"
        return Groq(model=model, api_key=os.getenv("GROQ_API_KEY"), temperature=temperature)
    
    elif provider == "openrouter":
        from llama_index.llms.openrouter import OpenRouter
        model = model_name or "deepseek/deepseek-v4-flash:free"
        return OpenRouter(model=model, api_key=os.getenv("OPENROUTER_API_KEY"), temperature=temperature)
    
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    
class ChatResponse:
    def __init__(self, response: str):
        self.response = response

class Chatbot:
    def __init__(self, index: VectorStoreIndex, provider: str = "groq", model_name: str = None, temperature: float = 0.7):
        self.index = index
        self.llm = llm_provider(provider=provider, model_name=model_name, temperature=temperature)

        self.system_prompt = (
            "You are a senior software developer an expert Codebase Exploration Agent. "
            "Your job is to help the user understand, debug, and architect solutions based on the repository. Reply naturally to greetings and non-code related questions."
            "If the user asks about the repository architecture, code, or documentation, "
            "use your available tools to search the codebase to find the answer. "
            "Always include code examples if relevant and format markdown properly."
        )
        self._agent = None
        self._memory = None

    def get_chat_engine(self, history : list = None):
        self._memory = ChatMemoryBuffer.from_defaults(token_limit=4000, chat_history=history or [])
        
        query_engine = self.index.as_query_engine(llm=self.llm, similarity_top_k=5)
        codebase_tool = QueryEngineTool(
            query_engine=query_engine,
            metadata=ToolMetadata(
                name="search_codebase", 
                description="Use this tool to search the repository for code, architecture, or documentation. NOT needed for general greetings or basic coding advice."
            )
        )
        
        self._agent = ReActAgent(
            tools=[codebase_tool],
            llm=self.llm,
            system_prompt=self.system_prompt,
            verbose=True,
        )
        #return self.index.as_chat_engine(chat_mode="condense_plus_context", memory=memory, llm=self.llm, system_prompt=self.system_prompt, verbose=True)
        return self
    
    @property
    def chat_history(self):
        if self._memory is None:
            return []
        return self._memory.get()
    
    async def chat(self, message: str) -> ChatResponse:
        handler = self._agent.run(user_msg=message, memory=self._memory)
        result = await handler
        return ChatResponse(response=result.response.content or "")
