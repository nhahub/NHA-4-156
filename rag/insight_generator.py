import os
import re
import json
from pathlib import Path

from llama_index.core import VectorStoreIndex
from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent


SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".vscode", ".idea", "target", "out", "bin", "obj",
}

INSIGHT_SYSTEM_PROMPT = (
    "You are a senior software developer producing an onboarding summary for a new "
    "engineer joining this codebase. You have access to these tools to explore the "
    "repository:\n"
    "- read_file: read the full content of a specific file\n"
    "- list_directory: see what files are in a directory\n"
    "- search_in_files: literal grep search across the codebase\n"
    "- get_repo_structure: overview of the repo layout\n\n"
    "Use get_repo_structure first to orient yourself, then read enough files (README, "
    "entrypoints, manifest/dependency files like requirements.txt or package.json, and "
    "the most important source files) to confidently answer. Reason and use tools as "
    "much as you need.\n\n"
    "Your FINAL message must contain ONLY a single valid JSON object - no markdown code "
    "fences, no commentary before or after it - with exactly these keys:\n\n"
    "{\n"
    '  "purpose": "2-3 sentence plain-English description of what this project does and who it is for",\n'
    '  "tech_stack": ["languages, frameworks, and key libraries actually found in the repo"],\n'
    '  "architecture": "1-2 paragraph description of how the major pieces fit together",\n'
    '  "key_files": [{"path": "relative/path", "purpose": "one sentence on what it is responsible for"}]\n'
    "}\n\n"
    "Base every field only on what you actually observed via your tools. If the repo is "
    "very small or sparse, say so honestly rather than inventing details."
)

INSIGHT_TASK_MESSAGE = (
    "Explore this repository and produce the onboarding summary. "
    "Your final reply must be ONLY the JSON object described in your instructions, nothing else."
)


def _make_llm(provider: str, model_name: str):
    if provider == "groq":
        from llama_index.llms.groq import Groq
        return Groq(
            model=model_name or "llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            is_function_calling_model=False,
        )
    elif provider == "openrouter":
        from llama_index.llms.openrouter import OpenRouter
        return OpenRouter(
            model=model_name or "deepseek/deepseek-v3-base:free",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            is_function_calling_model=False,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _make_tools(repo_path: Path) -> list:
    tools = []

    def read_file(file_path: str) -> str:
        """Read the full content of a file from the repository."""
        for candidate in [
            repo_path / file_path.lstrip("/"),
            repo_path / file_path,
            repo_path / file_path.lstrip("/").lstrip("\\"),
        ]:
            if candidate.exists() and candidate.is_file():
                return candidate.read_text(encoding="utf-8", errors="replace")
        return f"File not found: {file_path}"

    tools.append(FunctionTool.from_defaults(
        fn=read_file,
        name="read_file",
        description="Read the full content of a file. Input: relative path like 'src/main.py'",
    ))

    def list_directory(path: str = "") -> str:
        """List files and directories in a repo directory."""
        target = repo_path / path if path else repo_path
        if not target.exists() or not target.is_dir():
            return f"Directory not found: {path or '.'}"
        items = [
            f"{child.name}/" if child.is_dir() else child.name
            for child in sorted(target.iterdir())
            if child.name not in SKIP_DIRS
        ]
        return "\n".join(items) if items else "(empty directory)"

    tools.append(FunctionTool.from_defaults(
        fn=list_directory,
        name="list_directory",
        description="List files and subdirectories. Empty string for repo root.",
    ))

    def search_in_files(pattern: str, file_extension: str = "") -> str:
        """Literal text search across the codebase."""
        matches = []
        for f in repo_path.rglob("*"):
            if f.is_file() and (not file_extension or f.suffix == file_extension):
                try:
                    for i, line in enumerate(
                        f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                    ):
                        if re.search(re.escape(pattern), line, re.IGNORECASE):
                            rel = f.relative_to(repo_path)
                            matches.append(f"{rel}:{i}: {line.strip()[:200]}")
                except Exception:
                    continue
        return "\n".join(matches[:50]) or "No matches found."

    tools.append(FunctionTool.from_defaults(
        fn=search_in_files,
        name="search_in_files",
        description="Grep across the codebase. Parameters: pattern (required), file_extension (optional, e.g. '.py').",
    ))

    def get_repo_structure(max_depth: int = 3) -> str:
        """Get the directory tree of the repository."""
        lines = []

        def walk(dir_path: Path, depth: int):
            if depth > max_depth:
                return
            try:
                children = sorted(dir_path.iterdir())
            except PermissionError:
                return
            for child in children:
                if child.name in SKIP_DIRS or child.name.startswith(".repo_snapshot"):
                    continue
                indent = "  " * depth
                if child.is_dir():
                    lines.append(f"{indent}{child.name}/")
                    walk(child, depth + 1)
                else:
                    lines.append(f"{indent}{child.name}")

        walk(repo_path, 0)
        return "\n".join(lines[:150]) or "(empty repository)"

    tools.append(FunctionTool.from_defaults(
        fn=get_repo_structure,
        name="get_repo_structure",
        description="Get the directory tree of the repository (default max depth 3). Call this first.",
    ))

    return tools


def _parse_agent_json(raw_text: str) -> dict:
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {
        "purpose": text,
        "tech_stack": [],
        "architecture": "",
        "key_files": [],
        "parse_warning": "Agent did not return valid JSON; raw response stored in 'purpose'.",
    }


async def generate_insight(
    repo_path: str,
    provider: str = "groq",
    model_name: str = None,
) -> dict:
    path = Path(repo_path)
    llm = _make_llm(provider, model_name)
    tools = _make_tools(path)

    agent = ReActAgent(
        streaming=False,
        tools=tools,
        llm=llm,
        system_prompt=INSIGHT_SYSTEM_PROMPT,
        verbose=True,
    )

    handler = agent.run(user_msg=INSIGHT_TASK_MESSAGE)
    result = await handler
    raw = result.response.content or ""

    data = _parse_agent_json(raw)
    data.setdefault("purpose", "")
    data.setdefault("tech_stack", [])
    data.setdefault("architecture", "")
    data.setdefault("key_files", [])
    return data