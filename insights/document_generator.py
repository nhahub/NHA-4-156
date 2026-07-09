import json
import re
from pathlib import Path

from llama_index.core.agent import ReActAgent
from rag.agent_tools import llm_provider, make_file_tools


DOCS_SYSTEM_PROMPT = (
    "You are a senior software developer generating documentation for a code repository. "
    "This repository can be written in ANY language or framework — Python, JavaScript, "
    "TypeScript, React, Java, Go, etc. Adapt to whatever you find.\n\n"
    "You have tools to read files and explore the structure. "
    "Use get_repo_structure first, then read the main source files "
    "(components, pages, services, utils, models, controllers — whatever exists).\n\n"
    "IMPORTANT — be efficient: you have a limited number of steps. Do NOT read every file. "
    "After get_repo_structure, pick 5-8 of the most important source files (the core module(s), "
    "main entry point, key components/classes) and read only those. Then produce your final answer. "
    "Do not use search_in_files unless necessary.\n\n"
    "Your FINAL message must contain ONLY a single valid JSON object with exactly these keys:\n\n"
    "{\n"
    "  \"functions\": [\n"
    "    {\"name\": \"get_current_user\", \"signature\": \"get_current_user(token: str)\", "
    "\"file\": \"security.py\", \"summary\": \"Decodes JWT, validates expiry, returns user object or raises 401.\"},\n"
    "    {\"name\": \"NeoWidget\", \"signature\": \"NeoWidget({ apiKey })\", "
    "\"file\": \"src/NASA/neo.js\", \"summary\": \"React component that fetches and displays near-Earth object data from the NASA API.\"}\n"
    "  ],\n"
    "  \"endpoints\": [\n"
    "    {\"method\": \"GET\", \"path\": \"/items/{item_id}\", \"description\": \"Fetch item by ID\", "
    "\"request_body\": \"none\"}\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- functions: list the most important functions, classes, AND components (React/Vue/Angular), "
    "max 25 total. This includes: exported functions, React components (function or class), "
    "custom hooks, utility functions, service/API wrapper functions, class methods on major classes. "
    "Each summary is 1-2 sentences explaining what it does. Use docstrings/comments when available, "
    "otherwise infer from the code and its usage.\n"
    "- endpoints: HTTP endpoints DEFINED in this repo's own backend code (FastAPI/Flask/Express/etc routes). "
    "Do NOT list external third-party APIs the repo merely calls (e.g. calling the NASA API is not "
    "an endpoint of this repo). If this repo is frontend-only with no backend routes of its own, "
    "return an empty endpoints array — that is expected and correct.\n"
    "- Never return an empty functions array if the repository has any source code files. "
    "Every repo has at least some functions or components worth documenting.\n"
    "- Base everything only on what you actually read in the files."
)

DOCS_TASK_MESSAGE = (
    "Explore this repository and return the JSON object with functions and endpoints. "
    "Your final reply must be ONLY the JSON object, nothing else."
)


def _parse_docs_json(raw_text: str) -> dict:
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
    return {}


async def generate_docs(repo_id: str, provider: str = "anthropic", model_name: str = None) -> dict:
    repo_path = Path("data/processed") / repo_id

    llm = llm_provider(provider=provider, model_name=model_name, is_function_calling_model=False)
    tools = make_file_tools(repo_path)

    agent = ReActAgent(
        streaming=False,
        tools=tools,
        llm=llm,
        system_prompt=DOCS_SYSTEM_PROMPT,
        verbose=True,
    )

    handler = agent.run(user_msg=DOCS_TASK_MESSAGE, max_iterations=40)
    result = await handler
    raw = result.response.content or ""

    parsed = _parse_docs_json(raw)
    if not parsed.get("functions") and not parsed.get("endpoints"):
        print(f"[docs_generator] Empty result. Raw LLM output was:\n{raw[:1000]}")

    functions = []
    for f in parsed.get("functions", []):
        if isinstance(f, dict) and f.get("name"):
            functions.append({
                "name":      str(f.get("name", "")),
                "signature": str(f.get("signature", "")),
                "file":      str(f.get("file", "")),
                "summary":   str(f.get("summary", "")),
            })

    endpoints = []
    for e in parsed.get("endpoints", []):
        if isinstance(e, dict) and e.get("path"):
            endpoints.append({
                "method":       str(e.get("method", "GET")).upper(),
                "path":         str(e.get("path", "")),
                "description":  str(e.get("description", "")),
                "request_body": str(e.get("request_body", "none")),
            })

    return {"functions": functions[:25], "endpoints": endpoints}