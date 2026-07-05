from pathlib import Path
from llama_index.core import VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent
from rag.agent_tools import llm_provider, make_file_tools
from rag.reranker import get_reranker

def _extract_answer(result: str) -> str:
    if not result:
        return ""

    result = result.strip()
    idx = result.lower().rfind("answer:")
    if idx != -1:
        return result[idx + len("Answer:"):].strip()
    if result.lower().startswith("thought:"):
        lines = result.split("\n")
        answer_lines = []
        recording = False
        for line in lines:
            stripped = line.strip()
            if stripped.lower().startswith("answer:"):
                answer_lines.append(stripped[len("answer:"):].strip() if len(stripped) > 7 else "")
                recording = True
            elif recording:
                answer_lines.append(stripped)
        if answer_lines:
            return "\n".join(answer_lines).strip()
    return result


class ChatResponse:
    def __init__(self, response: str):
        self.response = response

class Chatbot:
    def __init__(self, index: VectorStoreIndex, repo_path: str = None, provider: str = "groq", model_name: str = None, temperature: float = 0.7):
        self.index = index
        self.repo_path = Path(repo_path) if repo_path else None
        self.llm = llm_provider(provider=provider, model_name=model_name, temperature=temperature, is_function_calling_model=False)

        self.system_prompt = (
            "You are a senior software developer and expert Codebase Exploration Agent. "
            "Reply naturally to greetings and non-code questions. "
            "When answering code questions, use your available tools to explore the repository:\n"
            "- search_codebase: semantic search for concepts, architecture, documentation\n"
            "- read_file: read the full content of a specific file\n"
            "- list_directory: see what files are in a directory\n"
            "- search_in_files: literal grep search across the codebase\n"
            "- get_repo_structure: overview of the repo layout\n"
            "Prefer reading actual files over relying solely on RAG snippets. "
            "Always include code examples and format markdown properly.\n"
            "CRITICAL: NEVER use <function> or <input> XML tags. "
            "You MUST use this exact format for tool calls:\n"
            "Thought: ...\nAction: tool_name\nAction Input: {...}"
        )
        self._agent = None
        self._memory = None

    def get_chat_engine(self, history : list = None):
        self._memory = ChatMemoryBuffer.from_defaults(token_limit=6000, chat_history=history or [])

        query_engine = self.index.as_query_engine(
            llm=self.llm, similarity_top_k=30,
            node_postprocessors=[get_reranker()]
        )
        codebase_tool = QueryEngineTool(
            query_engine=query_engine,
            metadata=ToolMetadata(
                name="search_codebase",
                description="Search the repository for code, architecture, or documentation using semantic search. Use this to find relevant files when you don't know exactly where something is."
            )
        )

        tools = [codebase_tool] + make_file_tools(self.repo_path)

        self._agent = ReActAgent(
            tools=tools,
            llm=self.llm,
            system_prompt=self.system_prompt,
            verbose=True,
        )
        return self

    @property
    def chat_history(self):
        if self._memory is None:
            return []
        return self._memory.get()

    async def chat(self, message: str) -> ChatResponse:
        handler = self._agent.run(user_msg=message, memory=self._memory)
        result = await handler
        clean = _extract_answer(result.response.content or "")
        return ChatResponse(response=clean)

    async def chat_stream(self, message: str):
        from llama_index.core.agent.workflow.workflow_events import (
            AgentStream,
            ToolCallResult,
        )

        yield {"type": "thinking", "data": {}}

        try:
            handler = self._agent.run(user_msg=message, memory=self._memory)
            raw_deltas = ""

            async for event in handler.stream_events():
                if isinstance(event, AgentStream):
                    if event.delta:
                        raw_deltas += event.delta
                        yield {"type": "thinking_delta", "data": {"text": event.delta}}
                    if event.tool_calls:
                        for tc in event.tool_calls:
                            yield {"type": "tool_call", "data": {"tool": tc.tool_name}}
                elif isinstance(event, ToolCallResult):
                    yield {"type": "tool_result", "data": {"text": str(event.tool_output.content)[:500]}}

            result = await handler
            clean = _extract_answer(raw_deltas)

            if clean:
                yield {"type": "token", "data": {"text": clean}}
            else:
                yield {"type": "token", "data": {"text": "Answer received."}}

            yield {"type": "done", "data": {}}
        except Exception as e:
            yield {"type": "error", "data": {"text": str(e)}}
