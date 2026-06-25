import os
import re
from pathlib import Path
from llama_index.core import VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import QueryEngineTool, ToolMetadata, FunctionTool
from llama_index.core.agent import ReActAgent
from rag.reranker import RepoReranker


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
    def __init__(self, index: VectorStoreIndex, repo_path: str = None, provider: str = "groq", model_name: str = None, temperature: float = 0.7):
        self.index = index
        self.repo_path = Path(repo_path) if repo_path else None
        self.llm = llm_provider(provider=provider, model_name=model_name, temperature=temperature)

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
            "Always include code examples and format markdown properly."
        )
        self._agent = None
        self._memory = None

    def _make_file_tools(self):
        tools = []

        def read_file(file_path: str) -> str:
            """Read the full content of a file from the repository."""
            if not self.repo_path:
                return "No repository path available."
            for candidate in [self.repo_path / file_path.lstrip("/"), self.repo_path / file_path, self.repo_path / file_path.lstrip("/").lstrip("\\")]:
                if candidate.exists() and candidate.is_file():
                    return candidate.read_text(encoding="utf-8", errors="replace")
            return f"File not found: {file_path}"

        tools.append(FunctionTool.from_defaults(
            fn=read_file,
            name="read_file",
            description="Read the full content of a file. Input: relative path like 'src/main.py' or 'api/routes/chat.py'"
        ))

        def list_directory(path: str = "") -> str:
            """List files and directories in a repo directory."""
            if not self.repo_path:
                return "No repository path available."
            target = self.repo_path / path if path else self.repo_path
            if not target.exists() or not target.is_dir():
                return f"Directory not found: {path or '.'}"
            items = []
            for child in sorted(target.iterdir()):
                items.append(f"{child.name}/" if child.is_dir() else child.name)
            return "\n".join(items) if items else "(empty directory)"

        tools.append(FunctionTool.from_defaults(
            fn=list_directory,
            name="list_directory",
            description="List files and subdirectories in a repo directory. Empty string for root. Input: relative path like 'api/routes'"
        ))

        def search_in_files(pattern: str, file_extension: str = "") -> str:
            """Literal text search across the codebase. Optionally filter by file extension like '.py'."""
            if not self.repo_path or not self.repo_path.exists():
                return "No repository path available."
            matches = []
            for f in self.repo_path.rglob("*"):
                if f.is_file() and (not file_extension or f.suffix == file_extension):
                    try:
                        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                            lowered = line.strip().lower()
                            if re.search(re.escape(pattern), lowered):
                                rel = f.relative_to(self.repo_path)
                                matches.append(f"{rel}:{i}: {line.strip()[:200]}")
                    except Exception:
                        continue
            return "\n".join(matches[:50]) or "No matches found."

        tools.append(FunctionTool.from_defaults(
            fn=search_in_files,
            name="search_in_files",
            description="Literal text grep across the codebase. Parameters: pattern (required, case-insensitive), file_extension (optional, e.g. '.py'). Returns up to 50 matches."
        ))

        def get_repo_structure(max_depth: int = 3) -> str:
            """Get the tree-like directory structure of the repository."""
            if not self.repo_path:
                return "No repository path available."
            lines = []
            skip_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".vscode", ".idea", "target", "out", "bin", "obj", ".repo_snapshot_hash"}

            def walk(dir_path: Path, depth: int):
                if depth > max_depth:
                    return
                for child in sorted(dir_path.iterdir()):
                    if child.name in skip_dirs:
                        continue
                    indent = "  " * depth
                    if child.is_dir():
                        lines.append(f"{indent}{child.name}/")
                        walk(child, depth + 1)
                    else:
                        lines.append(f"{indent}{child.name}")
            walk(self.repo_path, 0)
            return "\n".join(lines[:100]) or "(empty repository)"

        tools.append(FunctionTool.from_defaults(
            fn=get_repo_structure,
            name="get_repo_structure",
            description="Get the directory tree of the repository (default max depth 3). Use this first to understand the project layout."
        ))

        return tools

    def get_chat_engine(self, history : list = None):
        self._memory = ChatMemoryBuffer.from_defaults(token_limit=4000, chat_history=history or [])

        query_engine = self.index.as_query_engine(
            llm=self.llm, similarity_top_k=20,
            node_postprocessors=[RepoReranker()]
        )
        codebase_tool = QueryEngineTool(
            query_engine=query_engine,
            metadata=ToolMetadata(
                name="search_codebase",
                description="Search the repository for code, architecture, or documentation using semantic search. Use this to find relevant files when you don't know exactly where something is."
            )
        )

        tools = [codebase_tool] + self._make_file_tools()

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
        return ChatResponse(response=result.response.content or "")
