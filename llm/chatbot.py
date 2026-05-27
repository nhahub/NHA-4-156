import os
from llama_index.core import VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer

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
    
class Chatbot:
    def __init__(self, index: VectorStoreIndex, provider: str = "groq", model_name: str = None, temperature: float = 0.7):
        self.index = index
        self.llm = llm_provider(provider=provider, model_name=model_name, temperature=temperature)

        self.system_prompt = (
            "You are a senior developer and codebase expert. "
            "Using the provided retrieved codebase context, answer the user's question accurately. "
            "If the answer is not in the codebase, state that you don't know based on the context. "
            "Always include code examples if relevant and format markdown properly."
        )

    def get_chat_engine(self, history : list = None):
        memory = ChatMemoryBuffer.from_defaults(token_limit=4000, chat_history=history or [])
        return self.index.as_chat_engine(chat_mode="condense_plus_context", memory=memory, llm=self.llm, system_prompt=self.system_prompt, verbose=True)