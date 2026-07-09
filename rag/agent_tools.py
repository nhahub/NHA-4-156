import os
import re
from pathlib import Path
from llama_index.core.tools import FunctionTool

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".vscode", ".idea", "target", "out", "bin", "obj",
    ".repo_snapshot_hash",
}


def llm_provider(provider: str = "openrouter", model_name: str = None, temperature: float = 0.7, **kwargs):
    if provider == "groq":
        from llama_index.llms.groq import Groq
        model = model_name or "llama-3.3-70b-versatile"
        return Groq(model=model, api_key=os.getenv("GROQ_API_KEY"), temperature=temperature, **kwargs)

    elif provider == "openrouter":
        from llama_index.llms.openrouter import OpenRouter
        model = model_name or os.getenv("OPENROUTER_MODEL") or "deepseek/deepseek-v3-base:free"
        return OpenRouter(model=model, api_key=os.getenv("OPENROUTER_API_KEY"), temperature=temperature, max_tokens=8192, **kwargs)

    elif provider == "anthropic":
        from llama_index.llms.anthropic import Anthropic
        model = model_name or os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-6"
        kwargs.pop("is_function_calling_model", None)
        return Anthropic(model=model, api_key=os.getenv("ANTHROPIC_API_KEY"), temperature=temperature, max_tokens=8192, **kwargs)

    raise ValueError(f"Unsupported provider: {provider}")


def make_file_tools(repo_path: Path) -> list:
    tools = []

    def read_file(file_path: str) -> str:
        """Read the full content of a file from the repository."""
        if not repo_path or not repo_path.exists():
            return "No repository path available."
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
        if not repo_path or not repo_path.exists():
            return "No repository path available."
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
        if not repo_path or not repo_path.exists():
            return "No repository path available."
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
        if not repo_path or not repo_path.exists():
            return "No repository path available."
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
        return "\n".join(lines[:100]) or "(empty repository)"

    tools.append(FunctionTool.from_defaults(
        fn=get_repo_structure,
        name="get_repo_structure",
        description="Get the directory tree of the repository (default max depth 3). Call this first.",
    ))

    return tools