import json
import re
from pathlib import Path

from llama_index.core.agent import ReActAgent
from rag.agent_tools import llm_provider, make_file_tools


DOCS_SYSTEM_PROMPT = (
    "You are a senior software developer generating documentation for a code repository. "
    "You have tools to read files and explore the structure. "
    "Use get_repo_structure first, then read the main source files.\n\n"
    "Your FINAL message must contain ONLY a single valid JSON object with exactly these keys:\n\n"
    "{\n"
    "  \"functions\": [\n"
    "    {\"name\": \"get_current_user\", \"signature\": \"get_current_user(token: str)\", "
    "\"file\": \"security.py\", \"summary\": \"Decodes JWT, validates expiry, returns user object or raises 401.\"}\n"
    "  ],\n"
    "  \"endpoints\": [\n"
    "    {\"method\": \"GET\", \"path\": \"/items/{item_id}\", \"description\": \"Fetch item by ID\", "
    "\"request_body\": \"none\"}\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- functions: the most important exported functions and classes, max 25. "
    "Each summary is 1-2 sentences. Use docstrings when available, otherwise infer from the code.\n"
    "- endpoints: all detected HTTP endpoints (FastAPI/Flask/Express routes etc). "
    "method is GET/POST/PUT/DELETE/PATCH. request_body describes the expected body shape "
    "from Pydantic models or TypeScript interfaces, or \"none\".\n"
    "- If the repo has no HTTP endpoints, return an empty endpoints array.\n"
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


async def generate_docs(repo_id: str, provider: str = "groq", model_name: str = None) -> dict:
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

    handler = agent.run(user_msg=DOCS_TASK_MESSAGE)
    result = await handler
    raw = result.response.content or ""

    parsed = _parse_docs_json(raw)

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